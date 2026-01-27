"""
Database connection and session management (legacy sync support).
This module is kept for backward compatibility but new code should use core.database.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator
from loguru import logger

from ..core.config import get_settings
from .base import Base

settings = get_settings()

# Create SQLAlchemy engine (sync - for legacy code)
engine = create_engine(
    settings.postgres_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False  # Set to True for SQL query logging
)

# Create SessionLocal class (sync - for legacy code)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function for FastAPI to get database session (sync - legacy).
    
    Note: New code should use core.dependencies.get_db_session() for async support.
    
    Usage:
        @app.get("/endpoint")
        def endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """
    Context manager for database session (sync - legacy).
    
    Note: New code should use async patterns with core.dependencies.get_db_session()
    
    Usage:
        with get_db_context() as db:
            db.query(...)
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """
    Initialize database - create tables if they don't exist (sync - legacy).
    
    Note: New code should use core.database.init_db() for async support.
    """
    # Import all models here to ensure they're registered
    from ..models.document import Document, DocumentChunk
    
    try:
        logger.info("Connecting to database and initializing schema...")
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        
        # Create tables (only creates if they don't exist)
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def check_pgvector_extension():
    """Check if pgvector extension is installed (sync - legacy)."""
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT * FROM pg_extension WHERE extname = 'vector';"
        ))
        if result.fetchone():
            logger.info("pgvector extension is installed")
            return True
        else:
            logger.warning("pgvector extension is NOT installed")
            logger.warning("Run: CREATE EXTENSION vector;")
            return False
