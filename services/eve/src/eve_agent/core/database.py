"""
Database configuration and models for Eve Agent
Uses SQLAlchemy with async PostgreSQL (asyncpg) and pgvector support
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from loguru import logger
from .config import get_settings

# Lazy initialization pattern (like ugc_video)
engine = None
async_session_maker: async_sessionmaker[AsyncSession] | None = None


def init_engine():
    """Initialize database engine (lazy initialization)"""
    global engine, async_session_maker
    if engine is None:
        settings = get_settings()
        # Convert postgresql:// to postgresql+asyncpg:// for async
        database_url = settings.postgres_url
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif not database_url.startswith("postgresql+asyncpg://"):
            # If it's already asyncpg, keep it; otherwise add asyncpg
            if "postgresql+" not in database_url:
                database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
        engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20
        )
        async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    return engine


async def init_db():
    """Initialize database - create tables if they don't exist and enable pgvector."""
    # Import all models here to ensure they're registered
    from ..models.document import Document, DocumentChunk
    from ..models.conversation import Conversation, Message
    from ..database.base import Base
    
    try:
        logger.info("Connecting to database and initializing schema...")
        
        # Ensure engine is initialized
        init_engine()
        assert engine is not None
        
        # Enable pgvector extension
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        
        # Create tables (only creates if they don't exist)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database schema initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def check_pgvector_extension():
    """Check if pgvector extension is installed."""
    init_engine()
    assert engine is not None
    
    async with engine.connect() as conn:
        result = await conn.execute(text(
            "SELECT * FROM pg_extension WHERE extname = 'vector';"
        ))
        row = result.fetchone()
        if row:
            logger.info("pgvector extension is installed")
            return True
        else:
            logger.warning("pgvector extension is NOT installed")
            logger.warning("Run: CREATE EXTENSION vector;")
            return False
