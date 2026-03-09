# AI Assistant Hub Odontológico

Sistema multi-agente para gestión operativa de consultorio odontológico. Orquestado con LangGraph, backend FastAPI, PostgreSQL + pgvector, y comunicación vía WhatsApp (Meta Cloud API).

## Arquitectura

```
[WhatsApp] → [Supervisor] → [A1: Comunicaciones | A2: Agendas | A3: Perfilamiento | A4: Contenido]
                                      ↓
                              [PostgreSQL + pgvector]
```

| Agente | Responsabilidad |
|--------|----------------|
| A1 Comunicaciones | Interfaz WhatsApp + RAG sobre el consultorio |
| A2 Agendas | Google Calendar, agendamiento reactivo y proactivo |
| A3 Perfilamiento | EHR + CRM, segmentación, consentimientos |
| A4 Contenido | Borradores para redes sociales + imágenes locales |

## Stack

- **Backend:** Python 3.11, FastAPI, LangGraph, LangChain
- **LLM:** Ollama local (llama3.1:8b) — configurable via `.env`
- **DB:** PostgreSQL 16 + pgvector (embeddings)
- **Imágenes:** Stable Diffusion via Diffusers (local)
- **Infra:** Docker Compose + Nginx

## Inicio rápido

```bash
# 1. Copiar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales reales

# 2. Levantar servicios
docker-compose up -d

# 3. Ejecutar migraciones
docker-compose exec backend alembic upgrade head

# 4. Poblar configuración de agentes
docker-compose exec backend python -m app.seed

# 5. Verificar estado
curl http://localhost/health
```

## Fases de desarrollo

| Fase | Estado | Descripción |
|------|--------|-------------|
| 1 | ✅ Completa | Fundación: infraestructura, DB, modelos, FastAPI |
| 2 | Pendiente | WhatsApp webhook + estado LangGraph |
| 3 | Pendiente | Agente A1: Comunicaciones + RAG |
| 4 | Pendiente | Agente A2: Agendas + Google Calendar |
| 5 | Pendiente | Agente A3: Perfilamiento de pacientes |
| 6 | Pendiente | Agente A4: Generador de contenido |
| 7 | Pendiente | Seguridad admin + RBAC + cifrado PHI |
| 8 | Pendiente | Frontend React (Admin Dashboard) |

## Estructura del proyecto

```
backend/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Pydantic Settings desde .env
│   ├── core/
│   │   ├── llm_factory.py   # Punto único de cambio de proveedor LLM
│   │   ├── database.py      # PostgreSQL + pgvector
│   │   ├── state.py         # GlobalHubState (Pydantic)
│   │   └── security.py      # JWT, SHA-256, AES-256, HMAC
│   ├── agents/              # A1, A2, A3, A4 + supervisor
│   ├── graph/               # Grafo LangGraph principal
│   ├── integrations/        # WhatsApp + Google Calendar
│   ├── rag/                 # Ingesta y retrieval pgvector
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   ├── api/v1/              # REST API endpoints
│   └── scheduler/           # APScheduler (tareas proactivas)
├── alembic/                 # Migraciones de BD
└── Dockerfile
```

## Variables de entorno clave

| Variable | Default | Descripción |
|----------|---------|-------------|
| `LLM_PROVIDER` | `ollama` | Proveedor LLM: ollama, openai, anthropic, groq |
| `OLLAMA_MODEL` | `llama3.1:8b` | Modelo Ollama |
| `DATABASE_URL` | — | URL asyncpg de PostgreSQL |
| `META_VERIFY_TOKEN` | — | Token de verificación webhook WhatsApp |
| `SECRET_KEY` | — | Clave JWT para admin API |

## Normativa

Cumple con **Ley 1581 de 2012** (Colombia) para tratamiento de datos personales y **Resolución 1995 de 1999** para historias clínicas electrónicas.

- Consentimiento digital con hash SHA-256 verificable
- Cifrado AES-256 para campos PHI
- Audit log inmutable de todas las acciones de agentes
- Borrado lógico de registros clínicos (nunca físico)

## License

MIT. See `LICENSE`.
