"""
FastAPI dependencies
"""
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import async_session_maker


async def get_db_session() -> AsyncSession:
    """Dependency for FastAPI endpoints to get database session"""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
