from fastapi import APIRouter, File, UploadFile, Form
from typing import List
from app.services.session_service import get_or_create_session
from app.services.s3_service import upload_to_s3

router = APIRouter()

@router.post("/upload")
async def upload_file(
    session_id: str = Form(...),
    type: str = Form(...),  # 'avatar' or 'apparel'
    files: List[UploadFile] = File(...)
):
    session = get_or_create_session(session_id)
    uploaded_urls = []
    
    for file in files:
        content = await file.read()
        extension = file.filename.split('.')[-1]
        url = upload_to_s3(content, "user_uploaded", extension=extension)
        uploaded_urls.append(url)
        
        if type == "avatar":
            session["avatars"].append(url)
            if session["stage"] == "AVATAR_SELECTION":
                session["stage"] = "APPAREL_UPLOAD"
        elif type == "apparel":
            session["apparel"].append(url)
            if session["avatars"]:
                session["stage"] = "SCENE_SELECTION"
    
    message = "Upload successful."
    if session["stage"] == "SCENE_SELECTION":
        message = "Assets received. I can now suggest some scenes. Say 'Suggest scenes' or describe what you want."
    
    return {
        "status": "success",
        "urls": uploaded_urls,
        "stage": session["stage"],
        "message": message
    }
