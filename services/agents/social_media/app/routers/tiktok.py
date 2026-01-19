"""
TikTok router - posting and token management endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.tiktok import (
    PostRequest,
    PostResponse,
    PostHistoryResponse,
    TokenRequest,
    TokenResponse
)
from app.services.tiktok_service import TikTokService

router = APIRouter()


def get_tiktok_service(
    session: AsyncSession = Depends(get_session)
) -> TikTokService:
    """Dependency to get TikTok service"""
    return TikTokService(session)


@router.post("/v1/tiktok/tokens/add", response_model=TokenResponse, tags=["tokens"])
async def add_token(
    request: TokenRequest,
    service: TikTokService = Depends(get_tiktok_service)
) -> TokenResponse:
    """
    Store TikTok access token for a user.
    
    - **user_id**: User ID from your system
    - **access_token**: TikTok access token with posting permissions
    """
    try:
        result = await service.add_token(request)
        return TokenResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/v1/tiktok/post", response_model=PostResponse, tags=["posting"])
async def post_to_tiktok(
    request: PostRequest,
    service: TikTokService = Depends(get_tiktok_service)
) -> PostResponse:
    """
    Post a video to TikTok.
    
    - **user_id**: User ID from your system
    - **video_url**: Publicly accessible video URL
    - **caption**: Video caption/description
    - **hashtags**: List of hashtags (without #)
    """
    try:
        return await service.post_video(request)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to post: {str(e)}")


@router.get("/v1/tiktok/posts/{user_id}", response_model=PostHistoryResponse, tags=["posting"])
async def get_user_posts(
    user_id: int,
    service: TikTokService = Depends(get_tiktok_service)
) -> PostHistoryResponse:
    """
    Get all TikTok posts for a user.
    
    - **user_id**: User ID from your system
    """
    try:
        result = await service.get_user_posts(user_id)
        return PostHistoryResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
