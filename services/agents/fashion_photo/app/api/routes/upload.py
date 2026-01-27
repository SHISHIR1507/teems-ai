"""
Upload router - File upload for avatars and apparel
"""
from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form
import sys
from pathlib import Path

# Add shared_libs to path for error standardization
current_file = Path(__file__).resolve()
shared_libs_dir = current_file.parent.parent.parent.parent.parent.parent / "platform" / "shared_libs"
if str(shared_libs_dir) not in sys.path:
    sys.path.insert(0, str(shared_libs_dir))

try:
    from pyshared.errors import raise_standard_error
except ImportError:
    # Fallback if shared libs not available
    def raise_standard_error(status_code, message, detail=None, field=None):
        raise HTTPException(status_code=status_code, detail=message)
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
from app.services.realtime_notifier import (
    notify_vision_analysis_started,
    notify_vision_analysis_completed,
)
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
            raise_standard_error(
                status_code=404,
                message="Session not found",
                detail=f"Session with ID '{session_id}' not found for this tenant"
            )
        
        if upload_type not in ["avatar", "apparel"]:
            raise_standard_error(
                status_code=400,
                message="Invalid upload_type",
                detail="upload_type must be 'avatar' or 'apparel'",
                field="upload_type"
            )
        
        # Validate files
        ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"}
        ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
        
        uploaded_urls = []
        
        for file in files:
            # Validate file is provided
            if not file.filename:
                raise_standard_error(
                    status_code=400,
                    message="File must have a filename",
                    field="file"
                )
            
            # Validate file type
            content_type = file.content_type or ""
            file_extension = "." + file.filename.split('.')[-1].lower() if '.' in file.filename else ""
            
            if content_type not in ALLOWED_IMAGE_TYPES and file_extension not in ALLOWED_EXTENSIONS:
                raise_standard_error(
                    status_code=400,
                    message="Invalid file type",
                    detail=f"Allowed formats: JPEG, PNG, GIF, WebP. Received: {content_type or file_extension or 'unknown'}",
                    field="file"
                )
            
            content = await file.read()
            
            # Validate file is not empty
            if len(content) == 0:
                raise_standard_error(
                    status_code=400,
                    message="File is empty",
                    detail=f"File '{file.filename}' is empty",
                    field="file"
                )
            
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
                # Notify vision analysis started
                await notify_vision_analysis_started(tenant_id, session_id, "apparel", s3_key)
                try:
                    vision_analysis = analyze_image(s3_url, mode="apparel")
                    await notify_vision_analysis_completed(
                        tenant_id, session_id, "apparel", success=True
                    )
                except Exception as e:
                    logger.error(f"Vision analysis error: {e}")
                    await notify_vision_analysis_completed(
                        tenant_id, session_id, "apparel", success=False, error=str(e)
                    )
                    vision_analysis = None
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
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )
