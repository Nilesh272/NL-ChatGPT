from functools import lru_cache
from typing import Optional, Tuple

from langchain_openai import ChatOpenAI

from src.config.settings import GROQ_BASE_URL, get_settings


def is_llm_available() -> bool:
    return bool(get_settings().resolved_llm_provider())


def get_llm_provider_label() -> str:
    """Human-readable provider for UI (e.g. groq, openai, none)."""
    p = get_settings().resolved_llm_provider()
    return p or "none"


def _resolve_credentials() -> Tuple[str, str, str]:
    """
    Returns (provider, api_key, base_url).
    base_url is empty for default OpenAI endpoint.
    """
    settings = get_settings()
    provider = settings.resolved_llm_provider()
    if provider == "groq":
        return provider, settings.groq_api_key.strip(), GROQ_BASE_URL
    if provider == "openai":
        return provider, settings.openai_api_key.strip(), ""
    return "", "", ""


@lru_cache
def get_chat_model(temperature: Optional[float] = None) -> ChatOpenAI:
    settings = get_settings()
    provider, api_key, base_url = _resolve_credentials()

    if not provider or not api_key:
        raise RuntimeError(
            "No LLM API key configured. Set GROQ_API_KEY and/or OPENAI_API_KEY in .env. "
            "Use LLM_PROVIDER=groq to force Groq, or LLM_PROVIDER=auto (default) to prefer Groq when set."
        )

    kwargs = {
        "model": settings.resolved_llm_model(),
        "temperature": settings.llm_temperature if temperature is None else temperature,
        "api_key": api_key,
        "max_tokens": 2048,
    }
    if base_url:
        kwargs["base_url"] = base_url

    return ChatOpenAI(**kwargs)
