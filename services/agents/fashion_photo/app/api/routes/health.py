"""
Health check router with dependency checks
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.dependencies import get_db_session
from app.core.config import get_settings
from app.services.s3_service import get_s3_client
from app.models.schemas import HealthResponse

router = APIRouter()


@router.get("/health", tags=["health"])
async def health(session: AsyncSession = Depends(get_db_session)):
    """
    Health check endpoint with dependency status checks.
    Returns detailed status of database, S3, and other dependencies.
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
    
    # Check S3 connectivity
    try:
        from botocore.exceptions import ClientError, BotoCoreError
        settings = get_settings()
        if hasattr(settings, 's3_bucket_name') and settings.s3_bucket_name:
            s3_client = get_s3_client()
            # Try to list bucket (head_bucket is lighter but list_objects_v2 is more reliable)
            s3_client.head_bucket(Bucket=settings.s3_bucket_name)
            dependencies["s3"] = "connected"
        else:
            dependencies["s3"] = "not_configured"
    except (ClientError, BotoCoreError) as e:
        dependencies["s3"] = f"error: {str(e)}"
        overall_status = "degraded"  # S3 is important but not critical for basic health
    except Exception as e:
        dependencies["s3"] = f"error: {str(e)}"
        overall_status = "degraded"  # S3 is important but not critical for basic health
    
    return {
        "status": overall_status,
        "service": "Fashion Photo Agent",
        "version": "1.0.0",
        "dependencies": dependencies
    }
