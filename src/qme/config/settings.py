"""Application settings loaded from environment variables / .env.

Field names map to the uppercase env vars listed in ``.env.example``.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the Question Metadata Engine."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM provider (pluggable: gemini free tier default, groq free alternative,
    # openai paid fallback, or any OpenAI-compatible endpoint via
    # llm_provider=custom + custom_base_url).
    # Keys are validated by the LLM gateway at call time, not at import, so CLI
    # and health checks work without a key during local development.
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    custom_base_url: str = ""
    custom_api_key: str = ""

    # Runtime
    environment: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 2

    # Model routing (Gemini free tier by default — flash-lite has the highest
    # free RPM and supports strict json_schema structured outputs, required by
    # our structured-output-only rule; gemini-3.8-flash is the heavier fallback
    # at only 5 req/min free; see docs/TECHNOLOGY_DECISIONS.md)
    model_classifier: str = "gemini-3.5-flash-lite"
    model_difficulty: str = "gemini-3.5-flash-lite"
    model_solution: str = "gemini-3.5-flash-lite"
    model_formula: str = "gemini-3.5-flash-lite"
    model_validator: str = "gemini-3.5-flash-lite"

    # Gateway retry policy (429 backoff + schema-miss retries)
    max_retries: int = 3
    retry_base_delay_sec: float = 1.0

    # Batch processing
    checkpoint_interval: int = 10

    # Directories
    input_dir: Path = Path("./data/input")
    output_dir: Path = Path("./data/output")
    checkpoint_dir: Path = Path("./data/checkpoints")


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor (reset with ``get_settings.cache_clear()``)."""
    return Settings()
