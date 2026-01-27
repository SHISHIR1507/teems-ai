"""
Health check endpoint with dependency checks
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.dependencies import get_db_session
from app.core.config import get_settings
from app.services.s3_service import s3_client
from app.services.slidespeak_client import get_slidespeak_client
from botocore.exceptions import ClientError, BotoCoreError

router = APIRouter()


@router.get("/health")
async def health_check(session: AsyncSession = Depends(get_db_session)):
    """
    Health check endpoint with dependency status checks.
    Returns detailed status of database, S3, SlideSpeak API, and other dependencies.
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
        from app.core.config import S3_BUCKET_NAME
        if S3_BUCKET_NAME:
            s3_client.head_bucket(Bucket=S3_BUCKET_NAME)
            dependencies["s3"] = "connected"
        else:
            dependencies["s3"] = "not_configured"
    except (ClientError, BotoCoreError) as e:
        dependencies["s3"] = f"error: {str(e)}"
        overall_status = "degraded"
    except Exception as e:
        dependencies["s3"] = f"error: {str(e)}"
        overall_status = "degraded"
    
    # Check SlideSpeak API connectivity (optional, external service)
    try:
        client = get_slidespeak_client()
        # Simple check - just verify client is initialized
        if client.api_key:
            dependencies["slidespeak_api"] = "configured"
        else:
            dependencies["slidespeak_api"] = "not_configured"
    except Exception as e:
        dependencies["slidespeak_api"] = f"error: {str(e)}"
        # External API is optional, don't mark as unhealthy
    
    return {
        "status": overall_status,
        "service": "Presentation Agent API",
        "version": "1.0.0",
        "dependencies": dependencies
    }
