"""
Posts router - list, get, delete
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.core.auth import AuthenticatedUser, require_tenant
from app.services.db_helpers import (
    get_tenant_posts,
    get_post,
    verify_post_ownership,
)
from sqlalchemy import delete
from app.core.database import Post

router = APIRouter()


@router.get("/v1/posts")
async def list_posts(
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session),
    platform: str = Query(None, description="Filter by platform (tiktok, facebook)"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List tenant's posts"""
    try:
        tenant_id = user.tenant_id
        posts = await get_tenant_posts(
            session, tenant_id, platform=platform, limit=limit, offset=offset
        )
        return {
            "posts": [
                {
                    "id": p.id,
                    "platform": p.platform,
                    "video_url": p.video_url,
                    "caption": p.caption,
                    "hashtags": p.hashtags.split(",") if p.hashtags else [],
                    "status": p.status,
                    "publish_id": p.publish_id,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                }
                for p in posts
            ],
            "count": len(posts),
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/posts/{post_id}")
async def get_post_detail(
    post_id: str,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session),
):
    """Get post details"""
    try:
        tenant_id = user.tenant_id
        post = await get_post(session, post_id, tenant_id)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        return {
            "id": post.id,
            "platform": post.platform,
            "video_url": post.video_url,
            "caption": post.caption,
            "hashtags": post.hashtags.split(",") if post.hashtags else [],
            "status": post.status,
            "publish_id": post.publish_id,
            "created_at": post.created_at.isoformat() if post.created_at else None,
            "updated_at": post.updated_at.isoformat() if post.updated_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/v1/posts/{post_id}")
async def delete_post(
    post_id: str,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session),
):
    """Delete post record (does not delete from platform)"""
    try:
        tenant_id = user.tenant_id
        if not await verify_post_ownership(session, post_id, tenant_id):
            raise HTTPException(status_code=404, detail="Post not found")
        
        await session.execute(
            delete(Post).where(
                Post.id == post_id,
                Post.tenant_id == tenant_id,
            )
        )
        return {"status": "deleted", "post_id": post_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
