"""
FastAPI dependencies
"""
from sqlalchemy.ext.asyncio import AsyncSession
from app.core import database as db_module


async def get_db_session() -> AsyncSession:
    """Get database session"""
    if db_module.async_session_maker is None:
        db_module.init_engine()
    assert db_module.async_session_maker is not None
    async with db_module.async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
