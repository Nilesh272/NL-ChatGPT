import os
from unittest.mock import patch

from src.config.settings import get_settings
from src.llm.client import get_llm_provider_label, is_llm_available


def test_auto_prefers_groq_when_groq_key_set():
    get_settings.cache_clear()
    with patch.dict(
        os.environ,
        {
            "GROQ_API_KEY": "gsk_test",
            "OPENAI_API_KEY": "sk_test",
            "LLM_PROVIDER": "auto",
            "LLM_MODEL": "",
        },
        clear=False,
    ):
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.resolved_llm_provider() == "groq"
        assert settings.resolved_llm_model() == "llama-3.3-70b-versatile"
        assert is_llm_available()
        assert get_llm_provider_label() == "groq"


def test_groq_ignores_openai_model_name_in_env():
    get_settings.cache_clear()
    with patch.dict(
        os.environ,
        {
            "GROQ_API_KEY": "gsk_test",
            "LLM_PROVIDER": "auto",
            "LLM_MODEL": "gpt-4o-mini",
        },
        clear=False,
    ):
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.resolved_llm_provider() == "groq"
        assert settings.resolved_llm_model() == "llama-3.3-70b-versatile"


def test_force_openai_provider():
    get_settings.cache_clear()
    with patch.dict(
        os.environ,
        {
            "GROQ_API_KEY": "gsk_test",
            "OPENAI_API_KEY": "sk_test",
            "LLM_PROVIDER": "openai",
        },
        clear=False,
    ):
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.resolved_llm_provider() == "openai"
        assert get_llm_provider_label() == "openai"
