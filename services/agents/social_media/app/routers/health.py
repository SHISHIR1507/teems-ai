"""
Health check router
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Health check endpoint"""
    return {"status": "ok", "service": "tiktok_posting_service"}
