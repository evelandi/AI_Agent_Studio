from langchain_core.language_models import BaseChatModel
from app.config import settings
from sqlalchemy.orm import Session


def get_agent_llm_override(agent_name: str, db: Session | None = None) -> str | None:
    """
    Consulta agent_configs para ver si el agente tiene un override de LLM.
    Retorna el provider override o None si usa el global.
    """
    if db is None:
        return None
    try:
        from app.models.agent_config import AgentConfig
        config = db.query(AgentConfig).filter(AgentConfig.agent_name == agent_name).first()
        if config and config.parameters:
            return config.parameters.get("llm_override")
    except Exception:
        pass
    return None


def get_llm(agent_name: str = "default", db: Session | None = None) -> BaseChatModel:
    """
    Retorna el LLM configurado para el agente indicado.
    Para cambiar de proveedor globalmente: modificar LLM_PROVIDER en .env
    Proveedores soportados: ollama, openai, anthropic, groq
    """
    provider = settings.llm_provider

    # Permite override por agente desde agent_configs
    agent_override = get_agent_llm_override(agent_name, db)
    if agent_override:
        provider = agent_override

    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=0.7,
        )
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
        )
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=settings.anthropic_model,
            api_key=settings.anthropic_api_key,
        )
    elif provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
        )
    else:
        raise ValueError(f"LLM provider no soportado: {provider}")


def get_embed_model():
    """Retorna el modelo de embeddings configurado (siempre Ollama por ahora)."""
    from langchain_ollama import OllamaEmbeddings
    return OllamaEmbeddings(
        model=settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
    )
