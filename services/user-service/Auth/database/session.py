from __future__ import annotations
from dotenv import load_dotenv  
load_dotenv()

import os  
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from loguru import logger

from ..config import get_settings
from ..models.user import Base


def get_engine():
    settings = get_settings()
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        try:
            database_url = settings.DATABASE_URL
        except AttributeError:
            raise ValueError("DATABASE_URL not found")
    
    engine = create_async_engine(  # ✅ ASYNC
        database_url,
        echo=settings.log_level == "debug",
        pool_pre_ping=True,
        pool_recycle=300,
    )
    return engine


def get_session_factory():
    engine = get_engine()
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async_session = get_session_factory()


async def init_db() -> None:
    engine = get_engine()
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("User database tables created successfully")


async def get_session() -> AsyncSession:  # ✅ ASYNC
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()