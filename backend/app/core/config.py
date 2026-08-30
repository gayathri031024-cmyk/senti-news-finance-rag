"""
Application configuration.

All configuration is sourced from environment variables (or a local .env
file for development). Nothing here is hardcoded — see .env.example for
the variables this app expects.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "SentiNews Finance RAG"
    APP_ENV: str = "development"
    API_V1_PREFIX: str = "/api"

    # CORS - comma separated list of allowed origins for the frontend
    CORS_ORIGINS: str = "http://localhost:5173"

    # Database
    DATABASE_URL: str = (
        "postgresql+psycopg://sentinews:sentinews@localhost:5432/sentinews"
    )

    # Ingestion (Phase 2) — chunking + upload limits.
    # Defaults are sized for financial reports: long enough to keep a table
    # or a few paragraphs together for later retrieval, short enough to
    # avoid diluting a chunk with unrelated content. See README for the
    # reasoning.
    CHUNK_SIZE: int = 1200
    CHUNK_OVERLAP: int = 200
    MAX_FILE_SIZE_MB: int = 25
    UPLOAD_DIR: str = "storage/uploads"

    # Embeddings (Phase 3)
    # "local" is a dependency-free, deterministic hashing-based embedding
    # used for offline dev/tests (see services/embeddings/local_provider.py
    # for why, and its limits). "openai" calls a real embeddings API and
    # needs EMBEDDING_API_KEY. EMBEDDING_DIMENSIONS must match whatever
    # the chosen model actually outputs — the pgvector column is created
    # with a fixed dimension in the migration, so changing this requires
    # a new migration if you switch to a differently-sized model.
    EMBEDDING_PROVIDER: str = "local"
    EMBEDDING_MODEL: str = "local-hashing-v1"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_DIMENSIONS: int = 384

    # Hybrid retrieval (Phase 3). See README for the reasoning behind
    # these defaults.
    VECTOR_WEIGHT: float = 0.6
    KEYWORD_WEIGHT: float = 0.4
    TOP_K: int = 5

    # RAG generation (Phase 4)
    # "local" is a dependency-free, no-API-key placeholder provider used
    # for offline dev/tests (see services/llm/local_provider.py — it does
    # NOT generate real grounded answers). "openai" calls a real chat
    # completions API and needs LLM_API_KEY. Reuses TOP_K / VECTOR_WEIGHT /
    # KEYWORD_WEIGHT above for retrieval — Phase 4 does not duplicate or
    # reconfigure Phase 3's retrieval settings.
    LLM_PROVIDER: str = "local"
    LLM_MODEL: str = "local-echo-v1"
    LLM_API_KEY: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — read once, reused across the app."""
    return Settings()
