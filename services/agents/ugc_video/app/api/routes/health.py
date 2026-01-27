"""
Health check endpoint with dependency checks
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.dependencies import get_db_session
from app.core.config import get_settings
from app.services.s3_utils import get_s3_client
from botocore.exceptions import ClientError

router = APIRouter()


@router.get("/health")
async def health_check(session: AsyncSession = Depends(get_db_session)):
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
        from app.services.s3_utils import get_s3_client
        from app.core.config import S3_BUCKET_NAME
        if S3_BUCKET_NAME:
            s3_client = get_s3_client()
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
    
    return {
        "status": overall_status,
        "service": "UGC Orchestrator API with DB & S3",
        "version": "2.0.0",
        "dependencies": dependencies
    }
