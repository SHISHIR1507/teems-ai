from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from ..config import Settings, get_settings


class Base(DeclarativeBase):
    pass


engine: AsyncEngine | None = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    global engine, async_session_factory
    if engine is None:
        settings = settings or get_settings()
        engine = create_async_engine(settings.database_url, echo=False, future=True)
        async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
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


BrandfetchSession = AsyncSession

