from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    env: str = "development"
    log_level: str = "info"

    brandfetch_api_key: str
    brandfetch_endpoint: str = "https://api.brandfetch.io/v2/brands/"

    database_url: str

    request_timeout_seconds: float = 30.0
    cache_ttl_seconds: int = 1800

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

