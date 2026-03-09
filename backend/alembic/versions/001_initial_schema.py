"""initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Habilitar extensión pgvector
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Tabla patients
    op.create_table(
        "patients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("segment", sa.String(50), nullable=True),
        sa.Column("channel_pref", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone"),
    )
    op.create_index("ix_patients_phone", "patients", ["phone"])
    op.create_index("ix_patients_id", "patients", ["id"])

    # Tabla clinical_records (PHI)
    op.create_table(
        "clinical_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("procedure_type", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("next_visit_due", sa.Date(), nullable=True),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clinical_records_id", "clinical_records", ["id"])

    # Tabla appointments
    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("google_event_id", sa.String(200), nullable=True),
        sa.Column("procedure_type", sa.String(100), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), server_default="scheduled"),
        sa.Column("created_by_agent", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_appointments_id", "appointments", ["id"])

    # Tabla consents
    op.create_table(
        "consents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("consent_type", sa.String(50), nullable=True),
        sa.Column("document_hash", sa.String(64), nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_or_channel", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consents_id", "consents", ["id"])

    # Tabla content_pieces
    op.create_table(
        "content_pieces",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(30), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("image_path", sa.String(500), nullable=True),
        sa.Column("topic", sa.String(200), nullable=True),
        sa.Column("target_segment", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_content_pieces_id", "content_pieces", ["id"])

    # Tabla audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("agent_name", sa.String(50), nullable=True),
        sa.Column("action", sa.String(100), nullable=True),
        sa.Column("patient_id", sa.Integer(), nullable=True),
        sa.Column("detail", JSONB, nullable=True),
        sa.Column("triggered_by", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_id", "audit_logs", ["id"])

    # Tabla agent_configs
    op.create_table(
        "agent_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_name", sa.String(50), nullable=False),
        sa.Column("parameters", JSONB, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_name"),
    )
    op.create_index("ix_agent_configs_agent_name", "agent_configs", ["agent_name"])

    # Tabla knowledge_chunks (vector store)
    op.execute("""
        CREATE TABLE knowledge_chunks (
            id SERIAL PRIMARY KEY,
            content TEXT NOT NULL,
            source VARCHAR(200),
            embedding vector(768),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_table("knowledge_chunks")
    op.drop_index("ix_agent_configs_agent_name", table_name="agent_configs")
    op.drop_table("agent_configs")
    op.drop_index("ix_audit_logs_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_content_pieces_id", table_name="content_pieces")
    op.drop_table("content_pieces")
    op.drop_index("ix_consents_id", table_name="consents")
    op.drop_table("consents")
    op.drop_index("ix_appointments_id", table_name="appointments")
    op.drop_table("appointments")
    op.drop_index("ix_clinical_records_id", table_name="clinical_records")
    op.drop_table("clinical_records")
    op.drop_index("ix_patients_phone", table_name="patients")
    op.drop_index("ix_patients_id", table_name="patients")
    op.drop_table("patients")
    op.execute("DROP EXTENSION IF EXISTS vector")
