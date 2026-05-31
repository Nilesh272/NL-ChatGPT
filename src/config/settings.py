from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LlmProvider = Literal["auto", "openai", "groq"]

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"

_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Use an absolute path so Streamlit/CWD differences don't break env loading.
        env_file=str(_REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM — OpenAI and/or Groq (OpenAI-compatible)
    openai_api_key: str = ""
    groq_api_key: str = ""
    llm_provider: LlmProvider = "auto"
    llm_model: str = ""
    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0)

    anthropic_api_key: str = ""
    tavily_api_key: str = ""
    perplexity_api_key: str = ""

    confidence_threshold_high: int = Field(default=8, ge=1, le=10)
    confidence_threshold_medium: int = Field(default=5, ge=1, le=10)
    max_refine_iterations: int = Field(default=2, ge=0, le=5)
    retrieval_top_k: int = Field(default=6, ge=1, le=20)

    retrieval_min_relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    retrieval_cache_ttl_seconds: int = Field(default=300, ge=0)
    use_mock_when_no_keys: bool = True

    def resolved_llm_provider(self) -> str:
        """Return active provider: groq, openai, or empty string if none configured."""
        if self.llm_provider == "groq":
            return "groq" if self.groq_api_key.strip() else ""
        if self.llm_provider == "openai":
            return "openai" if self.openai_api_key.strip() else ""
        # auto: prefer Groq when key is set, else OpenAI
        if self.groq_api_key.strip():
            return "groq"
        if self.openai_api_key.strip():
            return "openai"
        return ""

    def resolved_llm_model(self) -> str:
        """Pick a model valid for the active provider (avoids e.g. gpt-4o-mini on Groq)."""
        provider = self.resolved_llm_provider()
        custom = self.llm_model.strip()

        if provider == "groq":
            if not custom or self._looks_like_openai_model(custom):
                return DEFAULT_GROQ_MODEL
            return custom

        if provider == "openai":
            if not custom:
                return DEFAULT_OPENAI_MODEL
            return custom

        return custom or DEFAULT_OPENAI_MODEL

    @staticmethod
    def _looks_like_openai_model(name: str) -> bool:
        lower = name.lower()
        return lower.startswith("gpt-") or lower.startswith("o1") or lower.startswith("o3")


@lru_cache
def get_settings() -> Settings:
    return Settings()
