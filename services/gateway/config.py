from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    env: str = Field(default="development", alias="ENV")
    log_level: str = Field(default="info", alias="LOG_LEVEL")

    # Downstream services
    eve_core_base_url: str = Field(..., alias="EVE_CORE_BASE_URL")
    agent_manager_base_url: str = Field(..., alias="AGENT_MANAGER_BASE_URL")
    realtime_ws_url: str = Field(default="ws://localhost:8096/ws", alias="REALTIME_WS_URL")

    # Auth0 (shared with user-service/Auth)
    auth0_domain: str = Field(..., alias="AUTH0_DOMAIN")
    auth0_audience: str = Field(..., alias="AUTH0_AUDIENCE")
    auth0_algorithm: str = Field(default="RS256", alias="AUTH0_ALGORITHM")

    # Redis for rate limiting and WS token forwarding metadata
    redis_url: Optional[str] = Field(default=None, alias="REDIS_URL")
    rate_limit_requests: int = Field(default=60, alias="RATE_LIMIT_REQUESTS")
    rate_limit_window_seconds: int = Field(default=60, alias="RATE_LIMIT_WINDOW_SECONDS")

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[arg-type]


