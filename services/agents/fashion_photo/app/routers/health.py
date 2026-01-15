from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def health():
    return {
        "status": "online",
        "service": "Fashion Photo Agent",
        "version": "1.0.0"
    }
