"""
Facebook posting service - business logic layer with tenant isolation
"""

from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Optional
from datetime import datetime

from app.services.db_helpers import (
    get_tenant_token,
    create_or_update_token,
    create_post,
    get_tenant_posts
)
from app.services.facebook_client import FacebookClient


class FacebookService:
    """Service for Facebook posting operations with tenant isolation"""
    
    def __init__(self, session: AsyncSession, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self.client = FacebookClient()
    
    async def add_token(
        self,
        user_id: Optional[str],
        access_token: str,
        page_id: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> dict:
        """Store or update tenant's Facebook access token"""
        token = await create_or_update_token(
            self.session,
            self.tenant_id,
            user_id,
            "facebook",
            access_token,
            refresh_token=None,  # Facebook tokens don't use refresh tokens the same way
            platform_user_id=page_id,  # Store page_id in platform_user_id field
            expires_at=expires_at
        )
        
        return {"status": "success", "message": "Token stored successfully"}
    
    async def post_video_async(
        self,
        user_id: str,
        video_url: str,
        caption: str,
        page_id: Optional[str] = None
    ) -> Dict:
        """Post video to Facebook (async)"""
        
        # 1. Get tenant's access token
        token_record = await get_tenant_token(self.session, self.tenant_id, "facebook")
        
        if not token_record:
            return {
                "status": "error",
                "error": f"No Facebook token found for tenant. Please connect your Facebook account via OAuth."
            }
        
        # 2. Determine target (page or user)
        # If page_id is provided, use it; otherwise use the stored page_id or user profile
        target_page_id = page_id or token_record.platform_user_id
        
        # 3. Post to Facebook
        try:
            result = self.client.post_video(
                video_url=video_url,
                caption=caption,
                access_token=token_record.access_token,
                page_id=target_page_id,
                user_id=None if target_page_id else user_id  # Only use user_id if no page
            )
            
            post_id = result.get("post_id")
            video_id = result.get("video_id")
            
            # 4. Save post record
            post = await create_post(
                self.session,
                conversation_id=None,
                tenant_id=self.tenant_id,
                user_id=user_id,
                platform="facebook",
                video_url=video_url,
                caption=caption,
                hashtags=None,  # Facebook doesn't use hashtags the same way
                publish_id=post_id,
                status="posted",
                extra={
                    "video_id": video_id,
                    "page_id": target_page_id
                }
            )
            
            return {
                "status": "success",
                "post_id": post_id,
                "video_id": video_id,
                "post_record_id": post.id,
                "message": "Posted to Facebook successfully",
                "posted_at": post.created_at.isoformat() if post.created_at else "",
            }
            
        except Exception as e:
            error_msg = str(e)
            return {
                "status": "error",
                "error": error_msg
            }
    
    async def get_posts_async(self, platform: str = "facebook", limit: int = 10) -> Dict:
        """Get tenant's posts"""
        posts = await get_tenant_posts(
            self.session,
            self.tenant_id,
            platform=platform,
            limit=limit,
            offset=0
        )
        
        return {
            "posts": [
                {
                    "id": p.id,
                    "platform": p.platform,
                    "video_url": p.video_url,
                    "caption": p.caption,
                    "hashtags": [],
                    "status": p.status,
                    "publish_id": p.publish_id,
                    "created_at": p.created_at.isoformat() if p.created_at else None
                }
                for p in posts
            ],
            "count": len(posts)
        }
