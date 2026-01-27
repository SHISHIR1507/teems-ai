"""
Health check endpoint with dependency checks
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.dependencies import get_db_session
from app.core.config import get_settings
from app.services.notification_service import get_redis

router = APIRouter()


@router.get("/health", tags=["health"])
async def health_check(session: AsyncSession = Depends(get_db_session)):
    """
    Health check endpoint with dependency status checks.
    Returns detailed status of database, Redis, and other dependencies.
    """
    dependencies = {}
    overall_status = "healthy"
    
    # Check database connectivity
    try:
        await session.execute(text("SELECT 1"))
        dependencies["database"] = "connected"
    except Exception as e:
        dependencies["database"] = f"error: {str(e)}"
        overall_status = "unhealthy"
    
    # Check Redis connectivity (optional for notifications)
    try:
        settings = get_settings()
        if hasattr(settings, 'redis_url') and settings.redis_url:
            redis_client = await get_redis()
            if redis_client:
                await redis_client.ping()
                dependencies["redis"] = "connected"
            else:
                dependencies["redis"] = "not_configured"
        else:
            dependencies["redis"] = "not_configured"
    except Exception as e:
        dependencies["redis"] = f"error: {str(e)}"
        # Redis is optional, so don't mark as unhealthy
    
    return {
        "status": overall_status,
        "service": "Notetaker Agent API",
        "version": "1.0.0",
        "dependencies": dependencies
    }
