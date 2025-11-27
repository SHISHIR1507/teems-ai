from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    auth0_domain: str
    auth0_audience: str
    auth0_client_id: str
    auth0_client_secret: str
    auth0_algorithm: str = "RS256"
    auth0_management_audience: str

    postgres_host: str | None = None
    postgres_port: int | None = 5432
    postgres_db: str | None = None
    postgres_user: str | None = None
    postgres_password: str | None = None

    aws_region: str | None = None
    aws_secret_arn: str | None = None

    log_level: str = "info"
    api_port: int = 8080

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    env_files = [file for file in (".env", ".env.local") if Path(file).exists()]
    if not env_files:
        # pydantic will still attempt to read .env even if missing, but this log clarifies.
        print("Warning: no .env file detected. Using shell environment variables.")  # noqa: T201
    return Settings()  # type: ignore[arg-type]

