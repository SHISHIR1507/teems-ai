from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    env: str = Field(default="development", alias="ENV")
    log_level: str = Field(default="info", alias="LOG_LEVEL")

    database_url: str = Field(..., alias="DATABASE_URL")
    vector_dimension: int = Field(default=1536, alias="VECTOR_DIMENSION")

    chunk_size: int = Field(default=750, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=150, alias="CHUNK_OVERLAP")

    embedding_provider: Literal["openai", "gemini"] = Field(default="openai", alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")

    default_llm_provider: Literal["openai", "gemini"] = Field(default="openai", alias="DEFAULT_LLM_PROVIDER")
    default_llm_model: str = Field(default="gpt-4o-mini", alias="DEFAULT_LLM_MODEL")

    top_k: int = Field(default=5, alias="TOP_K")

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[arg-type]

