"""
Health check router
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["health"])
async def health():
    """Minimal health check: returns online if service is running."""
    return {
        "status": "online",
        "service": "Fashion Photo Agent",
        "version": "1.0.0",
    }
