"""
Upload router - File upload for avatars and apparel
"""
from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.dependencies import get_db_session
from app.core.auth import AuthenticatedUser, require_tenant
from app.models.schemas import UploadResponse
from app.services.db_helpers import (
    get_session,
    create_avatar,
    create_apparel,
    update_session_stage
)
from app.services.s3_service import upload_to_s3
from app.tools.vision_tools import analyze_image
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger("routes.upload")


@router.post("/v1/upload", response_model=UploadResponse, tags=["upload"])
async def upload_file(
    session_id: str = Form(...),
    upload_type: str = Form(...),  # 'avatar' or 'apparel'
    files: List[UploadFile] = File(...),
    user: AuthenticatedUser = Depends(require_tenant()),
    db: AsyncSession = Depends(get_db_session)
) -> UploadResponse:
    """
    Upload avatar or apparel images.
    
    Supports multiple files. Files are uploaded to S3 and stored in the database.
    For apparel, vision analysis is automatically performed.
    """
    try:
        tenant_id = user.tenant_id
        
        # Verify session exists
        fashion_session = await get_session(db, session_id, tenant_id)
        if not fashion_session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if upload_type not in ["avatar", "apparel"]:
            raise HTTPException(status_code=400, detail="upload_type must be 'avatar' or 'apparel'")
        
        uploaded_urls = []
        
        for file in files:
            content = await file.read()
            extension = file.filename.split('.')[-1] if file.filename else "png"
            
            folder_type = "user_uploaded"
            s3_url = upload_to_s3(content, folder_type, extension=extension)
            s3_key = s3_url.split('/')[-1]
            uploaded_urls.append(s3_url)
            
            if upload_type == "avatar":
                await create_avatar(
                    db, session_id, tenant_id, s3_url, s3_key,
                    user.sub, avatar_type="uploaded"
                )
                if fashion_session.stage == "AVATAR_SELECTION":
                    await update_session_stage(db, session_id, tenant_id, "SCENE_SUGGESTION")
            elif upload_type == "apparel":
                vision_analysis = analyze_image(s3_url, mode="apparel")
                await create_apparel(
                    db, session_id, tenant_id, s3_url, s3_key,
                    user.sub, filename=file.filename,
                    file_size=len(content),
                    content_type=file.content_type,
                    vision_analysis=vision_analysis,
                )
                if fashion_session.stage in ("CONVERSATION", "APPAREL_SELECTION"):
                    await update_session_stage(db, session_id, tenant_id, "AVATAR_SELECTION")
        
        fashion_session = await get_session(db, session_id, tenant_id)
        message = "Upload successful."
        if upload_type == "apparel":
            message = "Apparel uploaded. Next, please upload or select an avatar."
        elif upload_type == "avatar" and fashion_session.stage == "SCENE_SUGGESTION":
            message = "Avatar set. I can suggest scenes—say “suggest scenes” or describe what you want."

        return UploadResponse(
            urls=uploaded_urls,
            session_id=session_id,
            upload_type=upload_type,
            stage=fashion_session.stage,
            message=message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in file upload: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
