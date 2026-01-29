"""
Application configuration and environment variables
"""
import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from typing import Optional

load_dotenv()

# Legacy settings for backward compatibility during migration
class LegacySettings:
    DATABASE_URL = os.getenv("DATABASE_URL")
    NYLAS_API_KEY = os.getenv("NYLAS_API_KEY")
    NYLAS_BASE_URL = os.getenv("NYLAS_BASE_URL", "https://api.us.nylas.com")
    AIML_API_KEY = os.getenv("AIML_API_KEY")
    AIML_BASE_URL = os.getenv("AIML_BASE_URL", "https://api.aimlapi.com/v1")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")

# Keep for backward compatibility
settings = LegacySettings()


class Settings(BaseSettings):
    """Application settings with validation"""
    
    # Database
    database_url: str = Field(..., alias="DATABASE_URL")
    
    # Nylas API
    nylas_api_key: str = Field(..., alias="NYLAS_API_KEY")
    nylas_base_url: str = Field(default="https://api.us.nylas.com", alias="NYLAS_BASE_URL")
    
    # AIML API (kept for backward compatibility)
    aiml_api_key: str = Field(default="", alias="AIML_API_KEY")
    aiml_base_url: str = Field(default="https://api.aimlapi.com/v1", alias="AIML_BASE_URL")
    
    # OpenAI API (for chat and embeddings)
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")
    llm_model: str = Field(default="gpt-4o", alias="LLM_MODEL")
    
    # Auth0 Configuration
    auth0_domain: str = Field(..., alias="AUTH0_DOMAIN")
    auth0_audience: str = Field(..., alias="AUTH0_AUDIENCE")
    auth0_algorithm: str = Field(default="RS256", alias="AUTH0_ALGORITHM")
    
    # Google Calendar OAuth Configuration
    google_client_id: str = Field(..., alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(..., alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field(..., alias="GOOGLE_REDIRECT_URI")
    
    # Encryption key for OAuth tokens (32 bytes base64 encoded)
    encryption_key: str = Field(..., alias="ENCRYPTION_KEY")
    
    # Redis Configuration (optional, for notifications)
    redis_url: Optional[str] = Field(None, alias="REDIS_URL")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
