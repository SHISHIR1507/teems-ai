from typing import AsyncGenerator

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from ..config import Settings, get_settings
from .base import Base

engine: AsyncEngine | None = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    global engine, async_session_factory
    if engine is None:
        settings = settings or get_settings()
        # Configure connection pool for high concurrency
        connect_args = {
            "server_settings": {
                "application_name": "onboarding_service",
            },
            "command_timeout": 10,  # 10 second timeout for commands
            "timeout": 10,  # 10 second connection timeout
        }
        engine = create_async_engine(
            settings.database_url,
            echo=False,
            future=True,
            pool_pre_ping=True,  # Verify connections before using
            pool_size=20,  # Base pool size
            max_overflow=40,  # Additional connections when needed
            pool_timeout=30,  # Wait up to 30s for connection from pool
            pool_recycle=3600,  # Recycle connections after 1 hour
            connect_args=connect_args,
        )
        async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
        logger.info("Database engine initialized with connection pool (size=20, max_overflow=40)")
    return engine


async def init_models() -> None:
    eng = get_engine()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if async_session_factory is None:
        get_engine()
    assert async_session_factory is not None
    async with async_session_factory() as session:
        yield session


OnboardingSession = AsyncSession

