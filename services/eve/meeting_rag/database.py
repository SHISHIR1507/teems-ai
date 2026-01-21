import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from sqlalchemy import text


sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import Base

load_dotenv()

# Get the database URL from .env (using your RDS)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in .env file")

# Create engine and session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

with engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    conn.commit()


# Create tables automatically
Base.metadata.create_all(bind=engine)
print(" Database tables created/verified")

def get_db():
    """Dependency for FastAPI endpoints"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()