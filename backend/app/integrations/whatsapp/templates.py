"""
Plantillas de mensajes de WhatsApp aprobadas por Meta.
Implementación completa: Fase 2
"""

APPOINTMENT_CONFIRMATION = {
    "name": "appointment_confirmation",
    "components": [
        {
            "type": "body",
            "parameters": [
                {"type": "text", "text": "{patient_name}"},
                {"type": "text", "text": "{procedure_type}"},
                {"type": "text", "text": "{appointment_date}"},
                {"type": "text", "text": "{appointment_time}"},
            ],
        }
    ],
}

APPOINTMENT_REMINDER = {
    "name": "appointment_reminder",
    "components": [
        {
            "type": "body",
            "parameters": [
                {"type": "text", "text": "{patient_name}"},
                {"type": "text", "text": "{days_until}"},
            ],
        }
    ],
}

CONSENT_REQUEST = """Hola {patient_name}, para continuar necesitamos tu autorización
para el tratamiento de datos personales según la Ley 1581 de 2012.

Para ACEPTAR responde: ACEPTO
Para más información sobre tus derechos, escribe: DERECHOS
"""
