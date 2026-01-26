"""
TikTok router - token add, post, post history
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.core.auth import AuthenticatedUser, require_tenant
from app.models.schemas import TokenRequest, TokenResponse, PostRequest, PostResponse, PostHistoryResponse
from app.services.tiktok_service import TikTokService

router = APIRouter()


def get_tiktok_service(
    session: AsyncSession = Depends(get_db_session),
    user: AuthenticatedUser = Depends(require_tenant()),
) -> TikTokService:
    return TikTokService(session, user.tenant_id)


@router.post("/v1/tiktok/tokens/add", response_model=TokenResponse)
async def add_tiktok_token(
    request: TokenRequest,
    service: TikTokService = Depends(get_tiktok_service),
    user: AuthenticatedUser = Depends(require_tenant()),
):
    """Store TikTok access token for the tenant. Requires auth + tenant."""
    try:
        result = await service.add_token(
            user_id=user.sub,
            access_token=request.access_token,
            refresh_token=request.refresh_token,
            platform_user_id=request.platform_user_id,
        )
        return TokenResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/v1/tiktok/post", response_model=PostResponse)
async def post_to_tiktok(
    request: PostRequest,
    service: TikTokService = Depends(get_tiktok_service),
    user: AuthenticatedUser = Depends(require_tenant()),
):
    """Post a video to TikTok. Requires auth + tenant."""
    try:
        result = await service.post_video_async(
            user_id=user.sub,
            video_url=request.video_url,
            caption=request.caption,
            hashtags=request.hashtags,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error", "Post failed"))
        post_id = result.get("post_id", "")
        publish_id = result.get("publish_id", "")
        return PostResponse(
            status="success",
            message=result.get("message", "Posted to TikTok successfully"),
            post_id=post_id,
            publish_id=publish_id,
            platform="tiktok",
            posted_at=result.get("posted_at", ""),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to post: {str(e)}")


@router.get("/v1/tiktok/posts", response_model=PostHistoryResponse)
async def get_tiktok_posts(
    service: TikTokService = Depends(get_tiktok_service),
    limit: int = Query(20, ge=1, le=100),
):
    """Get TikTok posts for the tenant. Requires auth + tenant."""
    try:
        result = await service.get_posts_async(platform="tiktok", limit=limit)
        posts = result.get("posts", [])
        return PostHistoryResponse(
            posts=[
                {
                    "id": p["id"],
                    "platform": p["platform"],
                    "video_url": p["video_url"],
                    "caption": p["caption"],
                    "hashtags": p["hashtags"],
                    "status": p["status"],
                    "publish_id": p["publish_id"],
                    "created_at": p["created_at"] or "",
                }
                for p in posts
            ],
            count=result.get("count", 0),
            limit=limit,
            offset=0,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
