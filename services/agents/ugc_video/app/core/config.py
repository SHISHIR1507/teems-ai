"""
Application configuration and environment variables
"""
import os
from dotenv import load_dotenv

load_dotenv()

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
