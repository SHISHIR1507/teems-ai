from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    env: str = "development"
    log_level: str = "info"

    # Database
    database_url: str

    # Redis for pubsub events
    redis_url: str | None = None

    # LLM Configuration (AIML API - kept for backward compatibility)
    aiml_api_key: str = ""
    aiml_base_url: str = "https://api.aimlapi.com/v1"
    
    # OpenAI Configuration
    openai_api_key: str
    openai_base_url: str = "https://api.openai.com/v1"
    default_llm_model: str = "openai/gpt-4o-mini"

    # Auth0
    auth0_domain: str = "teems.us.auth0.com"
    auth0_audience: str
    auth0_algorithm: str = "RS256"

    # Internal Service URLs
    brandfetch_api_url: str = "http://localhost:8095"

    # Onboarding Configuration
    onboarding_channel_prefix: str = "onboarding"

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    env_files = [file for file in (".env", ".env.local") if Path(file).exists()]
    if not env_files:
        print("Warning: Onboarding service running without .env file.")
    return Settings()

