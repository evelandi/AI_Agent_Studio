from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class IntentType(str, Enum):
    SCHEDULING = "scheduling"
    COMMUNICATION = "communication"
    PROFILING = "profiling"
    CONTENT = "content"
    UNKNOWN = "unknown"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    role: MessageRole
    content: str
    timestamp: Optional[str] = None


class GlobalHubState(BaseModel):
    """Estado global compartido entre todos los agentes del hub."""

    # Contexto de conversación
    conversation_id: str
    patient_phone: Optional[str] = None
    patient_id: Optional[int] = None
    current_intent: IntentType = IntentType.UNKNOWN
    messages: List[Message] = Field(default_factory=list)

    # Datos de trabajo entre agentes
    retrieved_context: Optional[str] = None       # RAG output
    pending_appointment: Optional[dict] = None    # Datos de cita en progreso
    awaiting_confirmation: bool = False

    # Control de flujo
    next_agent: Optional[str] = None
    error_message: Optional[str] = None
    requires_human_escalation: bool = False

    # Metadatos
    session_start: Optional[str] = None
    last_activity: Optional[str] = None
