from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    env: str = "development"
    log_level: str = "info"

    brandfetch_api_key: str
    brandfetch_endpoint: str = "https://api.brandfetch.io/v2/brands/"

    database_url: str
    redis_url: str | None = None

    request_timeout_seconds: float = 30.0
    cache_ttl_seconds: int = 1800
    onboarding_channel_prefix: str = "onboarding"

    # LLM (AIML API compatible)
    aiml_api_key: str | None = None
    aiml_base_url: str = "https://api.aimlapi.com/v1"
    default_llm_model: str = "openai/gpt-4o-mini"

    # Auth0 (to deduce tenant/user from tokens)
    auth0_domain: str = "teems.us.auth0.com"
    auth0_audience: str
    auth0_algorithm: str = "RS256"

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    env_files = [file for file in (".env", ".env.local") if Path(file).exists()]
    if not env_files:
        print("Warning: BrandfetchAPI running without .env file.")  # noqa: T201
    return Settings()  # type: ignore[arg-type]

