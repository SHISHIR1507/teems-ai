"""
Avatar router - Avatar selection and management
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db_session
from app.core.auth import AuthenticatedUser, require_tenant
from app.models.schemas import AvatarRequest, AvatarResponse, AvatarListResponse
from app.services.db_helpers import (
    get_session,
    create_avatar,
    get_session_avatars,
    update_session_stage
)
from app.services.s3_service import upload_to_s3
from app.core.logging import get_logger
import requests

router = APIRouter()
logger = get_logger("routes.avatar")


@router.post("/v1/avatars", response_model=AvatarResponse, tags=["avatars"])
async def select_avatar(
    request: AvatarRequest,
    user: AuthenticatedUser = Depends(require_tenant()),
    db: AsyncSession = Depends(get_db_session)
) -> AvatarResponse:
    """
    Select or upload an avatar for a session.
    
    If avatar_url is provided, it's treated as a preset avatar.
    Otherwise, expects file upload (handled separately via upload endpoint).
    """
    try:
        tenant_id = user.tenant_id
        session_id = request.session_id
        
        # Verify session exists
        fashion_session = await get_session(db, session_id, tenant_id)
        if not fashion_session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # If preset avatar URL provided
        if request.avatar_url:
            # Download and upload to S3 for consistency
            try:
                response = requests.get(request.avatar_url, timeout=30)
                response.raise_for_status()
                img_data = response.content
                s3_url = upload_to_s3(img_data, "user_uploaded", "png")
                s3_key = s3_url.split('/')[-1]
                
                avatar = await create_avatar(
                    db, session_id, tenant_id, s3_url, s3_key,
                    user.sub, avatar_type="preset", preset_url=request.avatar_url
                )
            except Exception as e:
                logger.error(f"Error processing preset avatar: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Failed to process avatar: {str(e)}")
        else:
            raise HTTPException(status_code=400, detail="avatar_url is required")
        
        if fashion_session.stage == "AVATAR_SELECTION":
            await update_session_stage(db, session_id, tenant_id, "SCENE_SUGGESTION")
        
        return AvatarResponse(
            id=avatar.id,
            session_id=avatar.session_id,
            s3_url=avatar.s3_url,
            avatar_type=avatar.avatar_type,
            created_at=avatar.created_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in avatar selection: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/avatars", response_model=AvatarListResponse, tags=["avatars"])
async def list_avatars(
    session_id: str,
    user: AuthenticatedUser = Depends(require_tenant()),
    db: AsyncSession = Depends(get_db_session)
) -> AvatarListResponse:
    """List all avatars for a session"""
    try:
        tenant_id = user.tenant_id
        avatars = await get_session_avatars(db, session_id, tenant_id)
        
        return AvatarListResponse(
            avatars=[
                AvatarResponse(
                    id=a.id,
                    session_id=a.session_id,
                    s3_url=a.s3_url,
                    avatar_type=a.avatar_type,
                    created_at=a.created_at.isoformat()
                )
                for a in avatars
            ],
            total=len(avatars)
        )
    except Exception as e:
        logger.error(f"Error listing avatars: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
