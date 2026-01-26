"""
Health check router
"""
from fastapi import APIRouter
from app.models.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health():
    """Health check endpoint"""
    return HealthResponse(
        status="online",
        service="Fashion Photo Agent",
        version="1.0.0"
    )
