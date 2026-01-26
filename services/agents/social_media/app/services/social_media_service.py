"""
Social Media Service - Multi-platform operations
"""

from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Optional

from app.services.db_helpers import (
    get_tenant_tokens,
    get_tenant_posts
)


class SocialMediaService:
    """Service for multi-platform social media operations"""
    
    def __init__(self, session: AsyncSession, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
    
    async def get_all_posts_async(self, platform: str = "all", limit: int = 10) -> Dict:
        """Get posts across all platforms or specific platform"""
        if platform == "all":
            # Get posts from all platforms
            posts = await get_tenant_posts(
                self.session,
                self.tenant_id,
                platform=None,  # None means all platforms
                limit=limit * 2,  # Get more to distribute across platforms
                offset=0
            )
            
            # Group by platform
            posts_by_platform = {}
            for post in posts:
                platform_name = post.platform
                if platform_name not in posts_by_platform:
                    posts_by_platform[platform_name] = []
                if len(posts_by_platform[platform_name]) < limit:
                    posts_by_platform[platform_name].append({
                        "id": post.id,
                        "platform": post.platform,
                        "video_url": post.video_url,
                        "caption": post.caption,
                        "hashtags": post.hashtags.split(",") if post.hashtags else [],
                        "status": post.status,
                        "publish_id": post.publish_id,
                        "created_at": post.created_at.isoformat() if post.created_at else None
                    })
        else:
            # Get posts from specific platform
            posts = await get_tenant_posts(
                self.session,
                self.tenant_id,
                platform=platform,
                limit=limit,
                offset=0
            )
            
            posts_by_platform = {
                platform: [
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
                ]
            }
        
        return {
            "posts_by_platform": posts_by_platform,
            "total_count": sum(len(posts) for posts in posts_by_platform.values())
        }
    
    async def get_connected_platforms_async(self) -> Dict:
        """Get list of platforms tenant has connected"""
        tokens = await get_tenant_tokens(self.session, self.tenant_id)
        
        platforms = [token.platform for token in tokens]
        
        return {
            "platforms": platforms,
            "count": len(platforms)
        }
