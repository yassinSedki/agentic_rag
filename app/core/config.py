"""Application configuration via pydantic-settings.

All settings are loaded from environment variables. Use ``get_settings()``
to obtain the cached singleton.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration — sourced from env vars / ``.env`` file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────
    app_env: Literal["dev", "staging", "prod"] = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # ── LLM (Ollama) ────────────────────────────────────────────────────
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "llama3"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_timeout_s: int = 60

    # ── Vector Database ──────────────────────────────────────────────────
    vector_db: Literal["chroma", "qdrant"] = "chroma"
    chroma_persistence_path: str = "./data/chroma_db"

    # ── Retrieval ────────────────────────────────────────────────────────
    top_k: int = 4
    max_context_chars: int = 12_000
    retrieval_timeout_s: int = 10

    # ── Chunking ─────────────────────────────────────────────────────────
    chunk_size: int = 512
    chunk_overlap: int = 64

    # ── Security ─────────────────────────────────────────────────────────
    rate_limit: str = "60/minute"

    # ── Observability ────────────────────────────────────────────────────
    otel_exporter_otlp_endpoint: str = "http://otel:4317"
    enable_pii_redaction: bool = True

    # ── Circuit Breaker ──────────────────────────────────────────────────
    circuit_breaker_threshold: int = 5
    circuit_breaker_reset_s: int = 30

    # ── Feature Flags ────────────────────────────────────────────────────
    enable_memory: bool = True  # Memory integration enabled


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton ``Settings`` instance."""
    return Settings()
