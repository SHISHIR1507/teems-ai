"""
TikTok posting service - business logic layer with tenant isolation
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Optional
from datetime import datetime

from app.services.db_helpers import (
    get_tenant_token,
    create_or_update_token,
    create_post,
    get_tenant_posts
)
from app.services.tiktok_client import TikTokClient


class TikTokService:
    """Service for TikTok posting operations with tenant isolation"""
    
    def __init__(self, session: AsyncSession, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self.client = TikTokClient()
    
    async def add_token(
        self,
        user_id: Optional[str],
        access_token: str,
        refresh_token: Optional[str] = None,
        platform_user_id: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> dict:
        """Store or update tenant's TikTok access token"""
        token = await create_or_update_token(
            self.session,
            self.tenant_id,
            user_id,
            "tiktok",
            access_token,
            refresh_token,
            platform_user_id,
            expires_at
        )
        
        return {"status": "success", "message": "Token stored successfully"}
    
    async def post_video_async(
        self,
        user_id: str,
        video_url: str,
        caption: str,
        hashtags: List[str] = None,
        conversation_id: Optional[str] = None,
    ) -> Dict:
        """Post video to TikTok (async)"""
        if hashtags is None:
            hashtags = []
        
        # 1. Get tenant's access token
        token_record = await get_tenant_token(self.session, self.tenant_id, "tiktok")
        
        if not token_record:
            return {
                "status": "error",
                "error": f"No TikTok token found for tenant. Please connect your TikTok account via OAuth."
            }
        
        # 2. Try posting with current token
        try:
            result = self.client.post_video(
                video_url=video_url,
                caption=caption,
                hashtags=hashtags,
                access_token=token_record.access_token
            )
            
            publish_id = result.get("publish_id")
            
            # 3. Save post record
            post = await create_post(
                self.session,
                conversation_id=conversation_id,
                tenant_id=self.tenant_id,
                user_id=user_id,
                platform="tiktok",
                video_url=video_url,
                caption=caption,
                hashtags=hashtags,
                publish_id=publish_id,
                status="posted",
                extra=result
            )
            
            return {
                "status": "success",
                "publish_id": publish_id,
                "post_id": post.id,
                "message": "Posted to TikTok successfully",
                "posted_at": post.created_at.isoformat() if post.created_at else "",
            }
            
        except Exception as e:
            error_msg = str(e)
            
            # Check if token expired (401)
            if "401" in error_msg or "token" in error_msg.lower():
                # Try refreshing token
                if token_record.refresh_token:
                    try:
                        refresh_result = await self.refresh_token_async()
                        if refresh_result.get("status") == "success":
                            new_access_token = refresh_result.get("access_token")
                            if not new_access_token:
                                token_record = await get_tenant_token(self.session, self.tenant_id, "tiktok")
                                new_access_token = token_record.access_token if token_record else None
                            if new_access_token:
                                result = self.client.post_video(
                                    video_url=video_url,
                                    caption=caption,
                                    hashtags=hashtags,
                                    access_token=new_access_token
                                )
                                publish_id = result.get("publish_id")
                                post = await create_post(
                                    self.session,
                                    conversation_id=None,
                                    tenant_id=self.tenant_id,
                                    user_id=user_id,
                                    platform="tiktok",
                                    video_url=video_url,
                                    caption=caption,
                                    hashtags=hashtags,
                                    publish_id=publish_id,
                                    status="posted",
                                    extra=result
                                )
                                return {
                                    "status": "success",
                                    "publish_id": publish_id,
                                    "post_id": post.id,
                                    "message": "Posted to TikTok successfully (token refreshed)",
                                    "posted_at": post.created_at.isoformat() if post.created_at else "",
                                }
                    except Exception:
                        pass
            
            return {
                "status": "error",
                "error": error_msg
            }
    
    async def refresh_token_async(self) -> Dict:
        """Refresh TikTok access token"""
        import requests
        import os
        from app.core.config import get_settings
        
        settings = get_settings()
        
        token_record = await get_tenant_token(self.session, self.tenant_id, "tiktok")
        if not token_record or not token_record.refresh_token:
            return {
                "status": "error",
                "error": "No refresh token available"
            }
        
        url = "https://open.tiktokapis.com/v2/oauth/token/"
        payload = {
            "client_key": settings.tiktok_client_key,
            "client_secret": settings.tiktok_client_secret,
            "grant_type": "refresh_token",
            "refresh_token": token_record.refresh_token
        }
        
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        try:
            response = requests.post(url, data=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                new_access_token = data.get("access_token")
                new_refresh_token = data.get("refresh_token")
                
                if not new_access_token:
                    return {
                        "status": "error",
                        "error": f"No access_token in response: {data}"
                    }
                
                # Update token in database
                await create_or_update_token(
                    self.session,
                    self.tenant_id,
                    token_record.user_id,
                    "tiktok",
                    new_access_token,
                    new_refresh_token or token_record.refresh_token,
                    token_record.platform_user_id
                )
                
                return {"status": "success", "message": "Token refreshed", "access_token": new_access_token}
            else:
                return {
                    "status": "error",
                    "error": f"Failed to refresh token (HTTP {response.status_code}): {response.text}"
                }
        except Exception as e:
            return {
                "status": "error",
                "error": f"Failed to refresh token: {str(e)}"
            }
    
    async def get_posts_async(self, platform: str = "tiktok", limit: int = 10) -> Dict:
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
                    "hashtags": p.hashtags.split(",") if p.hashtags else [],
                    "status": p.status,
                    "publish_id": p.publish_id,
                    "created_at": p.created_at.isoformat() if p.created_at else None
                }
                for p in posts
            ],
            "count": len(posts)
        }
