"""
FastAPI dependencies
"""
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import async_session_maker, init_engine


async def get_db_session() -> AsyncSession:
    """Get database session"""
    # Ensure engine is initialized
    if async_session_maker is None:
        init_engine()
    
    assert async_session_maker is not None
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
