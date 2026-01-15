import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL")
    NYLAS_API_KEY = os.getenv("NYLAS_API_KEY")
    NYLAS_BASE_URL = os.getenv("NYLAS_BASE_URL", "https://api.us.nylas.com")
    AIML_API_KEY = os.getenv("AIML_API_KEY")
    AIML_BASE_URL = os.getenv("AIML_BASE_URL", "https://api.aimlapi.com/v1")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")

settings = Settings()
