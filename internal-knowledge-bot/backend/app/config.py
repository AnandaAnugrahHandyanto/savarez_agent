from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "Internal Knowledge Bot API"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 720

    database_url: str = "sqlite:///./knowledge_bot.db"

    embedding_dim: int = 256
    top_k_default: int = 8
    min_confidence_for_auto_answer: float = 0.22
    chunk_size_chars: int = 900
    chunk_overlap_chars: int = 120

    hybrid_semantic_weight: float = 0.75
    hybrid_keyword_weight: float = 0.20
    hybrid_freshness_weight: float = 0.05

    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"

    # v2.1+/v3 ops controls
    default_handoff_sla_minutes: int = 24 * 60
    freshness_http_timeout_seconds: int = 3
    ingestion_worker_enabled: bool = False
    ingestion_worker_interval_seconds: int = 15

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
