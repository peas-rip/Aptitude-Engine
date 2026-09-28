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

    # Required for LLM stages (validated by the LLM gateway, not at import,
    # so CLI and health checks work without a key during local development).
    openai_api_key: str = ""

    # Runtime
    environment: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 2

    # Model routing (cost control: 4o-mini for cheap stages, 4o for complex)
    model_classifier: str = "gpt-4o-mini"
    model_difficulty: str = "gpt-4o-mini"
    model_solution: str = "gpt-4o"
    model_formula: str = "gpt-4o-mini"
    model_validator: str = "gpt-4o"

    # Batch processing
    checkpoint_interval: int = 10
    max_retries: int = 3

    # Directories
    input_dir: Path = Path("./data/input")
    output_dir: Path = Path("./data/output")
    checkpoint_dir: Path = Path("./data/checkpoints")


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor (reset with ``get_settings.cache_clear()``)."""
    return Settings()
