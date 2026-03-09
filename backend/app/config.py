from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Base de datos ──────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://hub_user:hub_password@localhost:5432/hub_db"
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg2://hub_user:hub_password@localhost:5432/hub_db"
    )

    # ── LLM ───────────────────────────────────────────────────
    llm_provider: Literal["ollama", "openai", "anthropic", "groq"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_embed_model: str = "nomic-embed-text"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    groq_api_key: str = ""
    groq_model: str = "llama-3.1-70b-versatile"

    # ── WhatsApp ──────────────────────────────────────────────
    meta_phone_number_id: str = ""
    meta_access_token: str = ""
    meta_verify_token: str = "my_verify_token_here"
    meta_app_secret: str = ""

    # ── Google Calendar ───────────────────────────────────────
    google_service_account_json: str = "./credentials/google_service_account.json"
    google_calendar_id: str = ""

    # ── LangSmith ─────────────────────────────────────────────
    langchain_tracing_v2: bool = True
    langchain_api_key: str = ""
    langchain_project: str = "ai-assistant-hub"

    # ── Seguridad ─────────────────────────────────────────────
    secret_key: str = "change_me_in_production"
    encryption_key: str = "change_me_in_production"

    # ── Generación de imágenes ────────────────────────────────
    image_model_id: str = "runwayml/stable-diffusion-v1-5"
    image_output_dir: str = "./storage/generated_images"

    # ── Aplicación ────────────────────────────────────────────
    environment: Literal["development", "production"] = "development"
    log_level: str = "INFO"


settings = Settings()
