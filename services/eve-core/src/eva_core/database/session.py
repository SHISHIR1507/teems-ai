from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

from ..config import Settings, get_settings
from .base import Base

engine = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(settings: Settings | None = None):
    global engine, async_session_factory
    if engine is None:
        settings = settings or get_settings()
        engine = create_async_engine(
            settings.database_url,
            echo=False,
            future=True,
            pool_pre_ping=True,
        )
        async_session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    return engine


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if async_session_factory is None:
        init_engine()
    assert async_session_factory is not None
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    eng = init_engine()
    async with eng.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

