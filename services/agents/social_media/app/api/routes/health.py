"""
Health check endpoint with dependency checks
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.dependencies import get_db_session
from app.core.config import get_settings

router = APIRouter()


@router.get("/health")
async def health_check(session: AsyncSession = Depends(get_db_session)):
    """
    Health check endpoint with dependency status checks.
    Returns detailed status of database and other dependencies.
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
    
    return {
        "status": overall_status,
        "service": "Social Media Agent API",
        "version": "1.0.0",
        "dependencies": dependencies
    }
