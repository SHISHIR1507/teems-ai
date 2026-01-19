"""
Async database session management
"""

from collections.abc import AsyncGenerator

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.core.config import Settings, get_settings

Base = declarative_base()

engine = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(settings: Settings | None = None):
    """Initialize async database engine"""
    global engine, async_session_factory
    if engine is None:
        settings = settings or get_settings()
        
        connect_args = {
            "server_settings": {
                "application_name": "tiktok_posting_service",
            },
            "command_timeout": 30,  # Increased timeout
            "timeout": 30,  # Increased connection timeout
        }
        
        engine = create_async_engine(
            settings.database_url,
            echo=False,
            future=True,
            pool_pre_ping=True,
            pool_timeout=30,
            connect_args=connect_args,
        )
        
        async_session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
        logger.info("Database engine initialized")
    
    return engine


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI to get async database session"""
    if async_session_factory is None:
        init_engine()
    assert async_session_factory is not None
    
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    """Initialize database schema"""
    eng = init_engine()
    try:
        logger.info("Connecting to database and initializing schema...")
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema initialized successfully")
    except Exception as e:
        logger.error(
            "Failed to initialize database: {}. Please check your DATABASE_URL.",
            str(e),
        )
        raise
