"""
Configuration management for Eve Agent using Pydantic Settings.
"""
import os
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Environment
    env: str = Field(default="development", alias="ENV")
    log_level: str = Field(default="info", alias="LOG_LEVEL")
    
    # Database Configuration
    postgres_url: str = Field(..., alias="DATABASE_URL")
    
    # PostgreSQL MCP Configuration (for restricted read-only access)
    postgres_mcp_user: str = Field(default="eve_mcp_readonly", alias="POSTGRES_MCP_USER")
    postgres_mcp_password: str = Field(..., alias="POSTGRES_MCP_PASSWORD")

    # Auth0 configuration (matches eve-core pattern)
    auth0_domain: str = Field(..., alias="AUTH0_DOMAIN")
    auth0_audience: str = Field(..., alias="AUTH0_AUDIENCE")
    auth0_algorithm: str = Field(default="RS256", alias="AUTH0_ALGORITHM")
    
    # AIML API Configuration (kept for OCR which stays on AIML)
    aiml_api_key: str = Field(default="", alias="AIML_API_KEY")
    aiml_base_url: str = Field(
        default="https://api.aimlapi.com/v1",
        alias="AIML_BASE_URL"
    )
    
    # OpenAI API Configuration (for chat and embeddings)
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        alias="OPENAI_BASE_URL"
    )
    
    # MCP Configuration
    tavily_api_key: str = Field(default="", alias="TAVILY_API")
    
    # Embedding Configuration
    embedding_provider: str = Field(default="openai", alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(
        default="text-embedding-3-small",
        alias="EMBEDDING_MODEL"
    )
    embedding_dimension: int = Field(default=1536, alias="EMBEDDING_DIMENSION")
    
    # LLM Configuration
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")
    llm_temperature: float = Field(default=0.7, alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=1000, alias="LLM_MAX_TOKENS")
    
    # AWS S3 Configuration
    aws_access_key_id: str = Field(default="", alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(default="", alias="AWS_SECRET_ACCESS_KEY")
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    s3_bucket_name: str = Field(default="", alias="S3_BUCKET_NAME")
    s3_folder_prefix: str = Field(default="UserUploads", alias="S3_FOLDER_PREFIX")
    
    # Chunking Configuration
    chunk_size: int = Field(default=350, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=50, alias="CHUNK_OVERLAP")
    
    # OCR Configuration
    ocr_enabled: bool = Field(default=True, alias="OCR_ENABLED")
    ocr_provider: str = Field(default="aiml", alias="OCR_PROVIDER")
    ocr_language: str = Field(default="en", alias="OCR_LANGUAGE")
    ocr_min_text_threshold: int = Field(default=100, alias="OCR_MIN_TEXT_THRESHOLD")
    
    # RAG Configuration
    rag_top_k: int = Field(default=5, alias="RAG_TOP_K")
    default_tenant_id: str = Field(default="default", alias="DEFAULT_TENANT_ID")
    
    # Redis Configuration (for realtime notifications)
    redis_url: str | None = Field(None, alias="REDIS_URL")
    
    # Agent Manager Configuration
    agent_manager_url: str = Field(default="http://agent-manager:8080", alias="AGENT_MANAGER_URL")
    
    # API Configuration
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=5000, alias="API_PORT")

    model_config = SettingsConfigDict(
        env_file=(".env", "../agent/.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[arg-type]
