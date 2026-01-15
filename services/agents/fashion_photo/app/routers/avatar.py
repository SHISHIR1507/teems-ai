from fastapi import APIRouter, Form
from app.services.session_service import get_or_create_session

router = APIRouter()

@router.post("/select_avatar")
async def select_avatar(
    session_id: str = Form(...),
    avatar_url: str = Form(...)
):
    session = get_or_create_session(session_id)
    session["avatars"].append(avatar_url)
    
    # Move to next stage if we have an avatar
    if session["stage"] == "AVATAR_SELECTION":
        session["stage"] = "APPAREL_UPLOAD"
    
    return {
        "status": "success",
        "message": "Avatar selected. Please upload apparel photos.",
        "stage": session["stage"]
    }
