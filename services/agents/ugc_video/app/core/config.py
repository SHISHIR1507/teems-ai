"""
Application configuration and environment variables
"""
import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from typing import List

load_dotenv()

# Backward compatibility: Keep direct env access for existing code
# LangSmith Configuration
LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "true")
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "ugc-orchestrator")

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL")

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "teems-agents")
S3_FOLDER_PREFIX = os.getenv("S3_FOLDER_PREFIX", "UGC_Agent")

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AIML_API_KEY = os.getenv("AIML_API_KEY")
BANANA_API_KEY = os.getenv("BANANA_API_KEY")
LIPSYNC_API_KEY = os.getenv("LIPSYNC_API_KEY")


# Settings class for dependency injection
class Settings(BaseSettings):
    """Application settings with validation"""
    
    # Database
    database_url: str = Field(..., alias="DATABASE_URL")
    
    # AWS S3
    aws_access_key_id: str | None = Field(None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(None, alias="AWS_SECRET_ACCESS_KEY")
    aws_region: str = Field(default="eu-north-1", alias="AWS_REGION")
    s3_bucket_name: str = Field(default="teems-agents", alias="S3_BUCKET_NAME")
    s3_folder_prefix: str = Field(default="UGC_Agent", alias="S3_FOLDER_PREFIX")
    
    # AI/ML API Keys
    openai_api_key: str | None = Field(None, alias="OPENAI_API_KEY")
    aiml_api_key: str = Field(..., alias="AIML_API_KEY")
    banana_api_key: str | None = Field(None, alias="BANANA_API_KEY")
    lipsync_api_key: str | None = Field(None, alias="LIPSYNC_API_KEY")
    
    # LangSmith Configuration
    langchain_tracing_v2: str = Field(default="true", alias="LANGCHAIN_TRACING_V2")
    langchain_project: str = Field(default="ugc-orchestrator", alias="LANGCHAIN_PROJECT")
    langchain_api_key: str | None = Field(None, alias="LANGCHAIN_API_KEY")
    
    # Auth0 Configuration
    auth0_domain: str = Field(..., alias="AUTH0_DOMAIN")
    auth0_audience: str = Field(..., alias="AUTH0_AUDIENCE")
    auth0_algorithm: str = Field(default="RS256", alias="AUTH0_ALGORITHM")
    
    # CORS Configuration
    cors_allowed_origins: str = Field(default="", alias="CORS_ALLOWED_ORIGINS")
    
    # Redis Configuration (for realtime notifications)
    redis_url: str | None = Field(None, alias="REDIS_URL")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


def get_cors_origins() -> List[str]:
    """Get CORS allowed origins from settings and environment"""
    # Default origins for local development and production fallback
    default_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "https://teems-web-app.vercel.app",
        "http://teems-web-app.vercel.app",
        "https://dev.teems.ai",
        "https://teems.ai",
    ]
    
    # Get from settings
    settings = get_settings()
    env_origins_str = settings.cors_allowed_origins or os.getenv("CORS_ALLOWED_ORIGINS", "")
    
    # Parse environment origins
    env_origins = []
    if env_origins_str:
        # Support both comma and space separated lists
        for part in env_origins_str.split(","):
            env_origins.extend(part.split())
        env_origins = [origin.strip() for origin in env_origins if origin.strip()]
    
    # Merge defaults with env origins, preserving order and de-duplicating
    all_origins = []
    seen = set()
    for origin in default_origins + env_origins:
        if origin not in seen:
            seen.add(origin)
            all_origins.append(origin)
    
    return all_origins
