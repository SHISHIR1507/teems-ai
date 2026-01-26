"""
Health check endpoint
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "Presentation Agent API",
        "version": "1.0.0",
        "database": "PostgreSQL",
        "storage": "AWS S3"
    }
