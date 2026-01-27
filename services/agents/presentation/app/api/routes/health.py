"""
Health check endpoint
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Minimal health check: returns ok if service is running."""
    return {
        "status": "ok",
        "service": "Presentation Agent API",
        "version": "1.0.0",
    }
