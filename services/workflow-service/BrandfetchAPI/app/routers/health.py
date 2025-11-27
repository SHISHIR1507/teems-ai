from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Service health probe")
async def health() -> dict[str, str]:
    return {"status": "ok"}

