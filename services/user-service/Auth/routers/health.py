from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Health probe")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}

