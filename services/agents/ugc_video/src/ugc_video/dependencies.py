from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .database.session import get_session
from .services.storage import S3StorageService, get_storage_service
from .config import get_settings


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


def get_storage_service_dep() -> S3StorageService:
    """FastAPI dependency for S3StorageService"""
    return get_storage_service()

