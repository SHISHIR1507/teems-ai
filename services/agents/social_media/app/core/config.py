"""
Configuration settings for the application
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Database
    database_url: str
    
    # AIML API
    aiml_api_key: str
    aiml_base_url: str
    llm_model: str
    
    # TikTok OAuth
    tiktok_client_key: str
    tiktok_client_secret: str
    oauth_redirect_uri: str = "https://teems-web-app.vercel.app/callback/tiktok"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

# Export settings for convenience (matches other agents pattern)
settings = get_settings()
