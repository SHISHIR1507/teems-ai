from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    database_url: str = Field(..., alias="DATABASE_URL")

    # Auth0
    auth0_domain: str = Field(..., alias="AUTH0_DOMAIN")
    auth0_audience: str = Field(..., alias="AUTH0_AUDIENCE")
    auth0_algorithm: str = Field(default="RS256", alias="AUTH0_ALGORITHM")
    
    
    # S3 (will be added later)
    # aws_access_key_id: str | None = None
    # aws_secret_access_key: str | None = None
    # s3_bucket_name: str | None = None
    # aws_region: str = "us-east-1"
    
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    env_files = [file for file in (".env", ".env.local") if Path(file).exists()]
    if not env_files:
        print("Warning: no .env file detected. Using shell environment variables.")
    return Settings()