from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    env: str = Field(default="development", alias="ENV")
    log_level: str = Field(default="info", alias="LOG_LEVEL")

    # Database / vector storage
    database_url: str = Field(..., alias="DATABASE_URL")
    vector_dimension: int = Field(default=1536, alias="VECTOR_DIMENSION")

    # Redis for events
    redis_url: str | None = Field(default=None, alias="REDIS_URL")

    # Chunking / retrieval
    chunk_size: int = Field(default=750, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=150, alias="CHUNK_OVERLAP")

    # Embedding / LLM providers
    embedding_provider: Literal["openai", "gemini"] = Field(
        default="openai", alias="EMBEDDING_PROVIDER"
    )
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")
    gemini_api_key: str = Field(default=None, alias="GEMINI_API_KEY")

    # AIML API configuration (used to access OpenAI / Gemini models via AIML)
    aiml_api_key: str = Field(..., alias="AIML_API_KEY")
    aiml_base_url: str = Field(
        default="https://api.aimlapi.com/v1",
        alias="AIML_BASE_URL",
        description="Base URL for AIML API-compatible OpenAI endpoint",
    )

    default_llm_provider: Literal["openai", "gemini"] = Field(
        default="openai", alias="DEFAULT_LLM_PROVIDER"
    )
    default_llm_model: str = Field(default="gpt-4o-mini", alias="DEFAULT_LLM_MODEL")

    top_k: int = Field(default=5, alias="TOP_K")

    # Auth0 configuration (shared with Auth service)
    auth0_domain: str = Field(..., alias="AUTH0_DOMAIN")
    auth0_audience: str = Field(..., alias="AUTH0_AUDIENCE")
    auth0_algorithm: str = Field(default="RS256", alias="AUTH0_ALGORITHM")

    # External services
    recommender_url: str | None = Field(default=None, alias="RECOMMENDER_URL")
    billing_url: str | None = Field(default=None, alias="BILLING_URL")

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[arg-type]

