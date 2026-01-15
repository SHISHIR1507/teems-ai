import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # LangSmith Configuration
    LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "true")
    LANGCHAIN_PROJECT = os.getenv("LANGSMITH_PROJECT", "photographer_agent")
    LANGCHAIN_API_KEY = os.getenv("LANGSMITH_API_KEY", "")
    
    # AWS Configuration
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_REGION = os.getenv("AWS_REGION")
    S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
    
    # API Keys
    AIML_API_KEY = os.getenv("AIML_API_KEY")
    
    # Preset Avatars
    PRESET_AVATARS = [
        "https://teems-agents.s3.eu-north-1.amazonaws.com/photographer_agent/person.png",
        "https://teems-agents.s3.eu-north-1.amazonaws.com/photographer_agent/Screenshot+from+2026-01-13+17-57-21.png",
        "https://teems-agents.s3.eu-north-1.amazonaws.com/photographer_agent/Screenshot+from+2026-01-13+17-56-52.png"
    ]

settings = Settings()
