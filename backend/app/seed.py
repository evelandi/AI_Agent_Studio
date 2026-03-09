"""
Script de seed: inserta los valores por defecto de agent_configs en la base de datos.
Ejecutar: python -m app.seed
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.database import SyncSessionLocal
from app.models.agent_config import AgentConfig

DEFAULT_CONFIGS = [
    {
        "agent_name": "communications",
        "parameters": {
            "tone": "cercano",
            "business_hours": {"start": "08:00", "end": "18:00"},
            "emergency_keywords": ["dolor", "urgencia", "accidente", "sangrado"],
            "auto_response_outside_hours": True,
            "human_escalation_threshold": 3,
        },
    },
    {
        "agent_name": "agenda",
        "parameters": {
            "procedure_durations": {
                "control": 30,
                "limpieza": 45,
                "ortodoncia": 30,
                "cirugia": 90,
                "implante": 120,
            },
            "buffer_minutes": 15,
            "emergency_slots_per_day": 2,
            "proactive_days_before": 5,
            "recurrence_tolerance_days": 3,
        },
    },
    {
        "agent_name": "profiling",
        "parameters": {
            "inactive_threshold_days": 180,
            "required_clinical_fields": ["procedure_type", "next_visit_due"],
            "segment_rules": {
                "cronic": {"recurrence_days": 30},
                "inactive": {"no_visit_days": 180},
                "high_value": ["implante", "rehabilitacion", "cirugia"],
            },
        },
    },
    {
        "agent_name": "content",
        "parameters": {
            "content_pillars": {"educational": 0.7, "promotional": 0.3},
            "brand_colors": ["#FFFFFF", "#0066CC"],
            "publication_frequency_days": 3,
            "specialties_focus": ["ortodoncia", "estetica"],
            "image_model": "runwayml/stable-diffusion-v1-5",
            "llm_override": None,
        },
    },
]


def seed() -> None:
    db = SyncSessionLocal()
    try:
        for config_data in DEFAULT_CONFIGS:
            existing = (
                db.query(AgentConfig)
                .filter(AgentConfig.agent_name == config_data["agent_name"])
                .first()
            )
            if existing:
                print(f"  [skip] {config_data['agent_name']} ya existe")
                continue
            db.add(AgentConfig(**config_data))
            print(f"  [ok]   {config_data['agent_name']} insertado")
        db.commit()
        print("\nSeed completado.")
    except Exception as e:
        db.rollback()
        print(f"Error en seed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
