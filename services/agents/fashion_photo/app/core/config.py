"""
Application configuration and environment variables
"""
import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache

load_dotenv()

# Preset Avatars (can be overridden via env)
DEFAULT_PRESET_AVATARS = [
    "https://teems-agents.s3.eu-north-1.amazonaws.com/photographer_agent/person.png",
    "https://teems-agents.s3.eu-north-1.amazonaws.com/photographer_agent/Screenshot+from+2026-01-13+17-57-21.png",
    "https://teems-agents.s3.eu-north-1.amazonaws.com/photographer_agent/Screenshot+from+2026-01-13+17-56-52.png"
]


class Settings(BaseSettings):
    """Application settings"""
    
    # Database
    database_url: str = Field(..., alias="DATABASE_URL")
    
    # AIML API
    aiml_api_key: str = Field(..., alias="AIML_API_KEY")
    aiml_base_url: str = Field(default="https://api.aimlapi.com/v1", alias="AIML_BASE_URL")
    llm_model: str = Field(default="openai/gpt-4o", alias="LLM_MODEL")
    
    # AWS S3
    aws_access_key_id: str | None = Field(None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(None, alias="AWS_SECRET_ACCESS_KEY")
    aws_region: str = Field(default="eu-north-1", alias="AWS_REGION")
    s3_bucket_name: str = Field(..., alias="S3_BUCKET_NAME")
    s3_folder_prefix: str = Field(default="Fashion_Photo_Agent", alias="S3_FOLDER_PREFIX")
    
    # Auth0
    auth0_domain: str = Field(..., alias="AUTH0_DOMAIN")
    auth0_audience: str = Field(..., alias="AUTH0_AUDIENCE")
    auth0_algorithm: str = Field(default="RS256", alias="AUTH0_ALGORITHM")
    
    # LangSmith Configuration (optional)
    langchain_tracing_v2: str = Field(default="true", alias="LANGCHAIN_TRACING_V2")
    langchain_project: str = Field(default="fashion_photo_agent", alias="LANGSMITH_PROJECT")
    langchain_api_key: str = Field(default="", alias="LANGSMITH_API_KEY")
    
    # Redis Configuration (for realtime notifications)
    redis_url: str | None = Field(None, alias="REDIS_URL")
    
    # Preset Avatars (can be set via env as comma-separated)
    preset_avatars: list[str] = Field(default_factory=lambda: DEFAULT_PRESET_AVATARS)
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Parse preset avatars from env if provided
        preset_avatars_env = os.getenv("PRESET_AVATARS", "")
        if preset_avatars_env:
            self.preset_avatars = [url.strip() for url in preset_avatars_env.split(",") if url.strip()]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Backward compatibility - keep settings instance
settings = get_settings()
