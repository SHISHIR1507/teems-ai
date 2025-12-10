from __future__ import annotations

from collections.abc import AsyncGenerator

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import Settings, get_settings
from .models import Base

engine = None
session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(settings: Settings | None = None):
    global engine, session_factory
    if engine is None:
        settings = settings or get_settings()
        engine = create_async_engine(
            settings.database_url,
            echo=False,
            future=True,
            pool_pre_ping=True,
        )
        session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
        logger.info("Vector store engine initialized")
    return engine


async def init_models() -> None:
    eng = init_engine()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if session_factory is None:
        init_engine()
    assert session_factory is not None
    async with session_factory() as session:
        yield session


