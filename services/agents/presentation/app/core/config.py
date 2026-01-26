"""
Application configuration and environment variables
"""
import os
from dotenv import load_dotenv

load_dotenv()

# SlideSpeak API Configuration
SLIDESPEAK_API_KEY = os.getenv("SLIDESPEAK_API_KEY")
SLIDESPEAK_BASE_URL = os.getenv("SLIDESPEAK_BASE_URL", "https://api.slidespeak.co/api/v1/")

# AIML API Configuration (for LLM)
AIML_API_KEY = os.getenv("AIML_API_KEY")
AIML_BASE_URL = os.getenv("AIML_BASE_URL", "https://api.aimlapi.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-4o")

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "teems-agents")
S3_FOLDER_PREFIX = os.getenv("S3_FOLDER_PREFIX", "Presentation_Agent")

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL")

# Webhook Configuration
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "https://api.teems.ai")

# Auth0 Configuration
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")
AUTH0_ALGORITHM = os.getenv("AUTH0_ALGORITHM", "RS256")

# LangSmith Configuration (optional)
LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "false")
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "presentation-agent")


# Settings class for dependency injection
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings"""
    
    # Database
    database_url: str = Field(..., alias="DATABASE_URL")
    
    # SlideSpeak API
    slidespeak_api_key: str = Field(..., alias="SLIDESPEAK_API_KEY")
    slidespeak_base_url: str = Field(default="https://api.slidespeak.co/api/v1/", alias="SLIDESPEAK_BASE_URL")
    
    # AIML API
    aiml_api_key: str = Field(..., alias="AIML_API_KEY")
    aiml_base_url: str = Field(default="https://api.aimlapi.com/v1", alias="AIML_BASE_URL")
    llm_model: str = Field(default="openai/gpt-4o", alias="LLM_MODEL")
    
    # AWS S3
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    s3_bucket_name: str = Field(..., alias="S3_BUCKET_NAME")
    s3_folder_prefix: str = Field(default="Presentation_Agent", alias="S3_FOLDER_PREFIX")
    
    # Auth0
    auth0_domain: str = Field(..., alias="AUTH0_DOMAIN")
    auth0_audience: str = Field(..., alias="AUTH0_AUDIENCE")
    auth0_algorithm: str = Field(default="RS256", alias="AUTH0_ALGORITHM")
    
    # Webhook
    webhook_base_url: str = Field(default="https://api.teems.ai", alias="WEBHOOK_BASE_URL")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
