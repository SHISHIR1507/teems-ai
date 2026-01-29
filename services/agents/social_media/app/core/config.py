"""
Application configuration and environment variables
"""
import os
from dotenv import load_dotenv
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache

load_dotenv()


class Settings(BaseSettings):
    """Application settings"""
    
    # Database
    database_url: str = Field(..., alias="DATABASE_URL")
    
    # AIML API (kept for backward compatibility)
    aiml_api_key: str = Field(default="", alias="AIML_API_KEY")
    aiml_base_url: str = Field(default="https://api.aimlapi.com/v1", alias="AIML_BASE_URL")
    
    # OpenAI API (for chat)
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    llm_model: str = Field(default="gpt-4o", alias="LLM_MODEL")
    
    # TikTok OAuth
    tiktok_client_key: str = Field(..., alias="TIKTOK_CLIENT_KEY")
    tiktok_client_secret: str = Field(..., alias="TIKTOK_CLIENT_SECRET")
    oauth_redirect_uri: str = Field(default="https://teems-web-app.vercel.app/callback/tiktok", alias="OAUTH_REDIRECT_URI")
    
    # Facebook OAuth (for future use)
    facebook_app_id: str = Field(default="", alias="FACEBOOK_APP_ID")
    facebook_app_secret: str = Field(default="", alias="FACEBOOK_APP_SECRET")
    facebook_redirect_uri: str = Field(default="https://teems-web-app.vercel.app/callback/facebook", alias="FACEBOOK_REDIRECT_URI")
    
    # AWS S3 Configuration (optional, for video storage)
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    s3_bucket_name: str = Field(default="teems-agents", alias="S3_BUCKET_NAME")
    s3_folder_prefix: str = Field(default="Social_Media_Agent", alias="S3_FOLDER_PREFIX")
    aws_access_key_id: str = Field(default="", alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(default="", alias="AWS_SECRET_ACCESS_KEY")
    
    # Auth0 Configuration
    auth0_domain: str = Field(..., alias="AUTH0_DOMAIN")
    auth0_audience: str = Field(..., alias="AUTH0_AUDIENCE")
    auth0_algorithm: str = Field(default="RS256", alias="AUTH0_ALGORITHM")
    
    # Redis Configuration (for realtime notifications)
    redis_url: Optional[str] = Field(None, alias="REDIS_URL")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
