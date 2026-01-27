"""
Content upload endpoint (image or video) for social media posting flow.
"""
import uuid
import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.core.auth import AuthenticatedUser, require_tenant
from app.models.schemas import UploadResponse
from app.services.db_helpers import (
    get_or_create_conversation,
    create_asset,
    update_conversation_state,
)
from app.services.s3_service import upload_bytes_to_s3, get_s3_key_for_content
from app.tools.vision_tools import analyze_content
from app.services.realtime_notifier import (
    notify_vision_analysis_started,
    notify_vision_analysis_completed,
)

router = APIRouter()

ALLOWED_IMAGE = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ALLOWED_VIDEO = {"video/mp4", "video/quicktime", "video/webm"}


def _infer_type(content_type: str, filename: str) -> str:
    if content_type in ALLOWED_IMAGE:
        return "image"
    if content_type in ALLOWED_VIDEO:
        return "video"
    ext = (Path(filename or "").suffix or "").lower()
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        return "image"
    if ext in {".mp4", ".mov", ".webm"}:
        return "video"
    return "video"


@router.post("/v1/upload", response_model=UploadResponse)
async def upload_content(
    file: UploadFile = File(..., description="Image or video file"),
    conversation_id: str = Form(None),
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session),
) -> UploadResponse:
    """
    Upload image or video for posting. Stored in S3 and linked to conversation.
    Returns asset_id, url, display_url for frontend display.
    """
    try:
        tenant_id = user.tenant_id
        cid = conversation_id or str(uuid.uuid4())
        await get_or_create_conversation(session, cid, tenant_id, user.sub)

        raw = await file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="Empty file")

        content_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
        asset_type = _infer_type(content_type, file.filename or "")
        s3_key = get_s3_key_for_content(cid, file.filename or "file", asset_type)

        s3_url = upload_bytes_to_s3(
            raw,
            s3_key,
            content_type=content_type,
            public_read=True,
        )

        # Create asset first (we'll update with vision_analysis later)
        asset = await create_asset(
            session=session,
            conversation_id=cid,
            tenant_id=tenant_id,
            user_id=user.sub,
            asset_type=asset_type,
            source="upload",
            s3_key=s3_key,
            s3_url=s3_url,
            file_name=file.filename,
            content_type=content_type,
        )

        # Notify vision analysis started
        await notify_vision_analysis_started(tenant_id, cid, asset.id, asset_type)

        # Analyze content with vision API (for images, and attempt for videos)
        vision_analysis = None
        error_msg = None
        try:
            vision_analysis = analyze_content(s3_url, asset_type=asset_type)
            # Update asset with vision analysis
            asset.vision_analysis = vision_analysis
            await session.flush()
            await notify_vision_analysis_completed(tenant_id, cid, asset.id, asset_type, success=True)
        except Exception as e:
            # If vision analysis fails, continue without it
            error_msg = str(e)
            await notify_vision_analysis_completed(tenant_id, cid, asset.id, asset_type, success=False, error=error_msg)

        await update_conversation_state(
            session, cid, tenant_id,
            stage="prepare_and_confirm",
            pending_asset_id=asset.id,
        )

        return UploadResponse(
            asset_id=asset.id,
            url=s3_url,
            display_url=s3_url,
            content_type=content_type,
            type=asset_type,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
