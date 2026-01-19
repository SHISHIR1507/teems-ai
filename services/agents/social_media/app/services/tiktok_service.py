"""
TikTok posting service - business logic layer
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tiktok import Post, UserToken
from app.schemas.tiktok import PostRequest, PostResponse, TokenRequest
from app.services.tiktok_client import TikTokClient
from datetime import datetime


class TikTokService:
    """Service for TikTok posting operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.client = TikTokClient()
    
    async def add_token(self, request: TokenRequest) -> dict:
        """Store or update user's TikTok access token"""
        
        # Check if token exists
        stmt = select(UserToken).where(
            UserToken.user_id == request.user_id,
            UserToken.platform == "tiktok"
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing token
            existing.access_token = request.access_token
            existing.updated_at = datetime.utcnow()
        else:
            # Create new token
            token = UserToken(
                user_id=request.user_id,
                platform="tiktok",
                access_token=request.access_token
            )
            self.session.add(token)
        
        await self.session.commit()
        
        return {"status": "success", "message": "Token stored successfully"}
    
    async def post_video(self, request: PostRequest) -> PostResponse:
        """Post video to TikTok"""
        
        # 1. Get user's access token
        stmt = select(UserToken).where(
            UserToken.user_id == request.user_id,
            UserToken.platform == "tiktok"
        )
        result = await self.session.execute(stmt)
        token_record = result.scalar_one_or_none()
        
        if not token_record:
            raise ValueError(f"No TikTok token found for user {request.user_id}")
        
        # 2. Post to TikTok API
        result = self.client.post_video(
            video_url=request.video_url,
            caption=request.caption,
            hashtags=request.hashtags,
            access_token=token_record.access_token
        )
        
        # 3. Save post record
        post = Post(
            user_id=request.user_id,
            platform="tiktok",
            video_url=request.video_url,
            caption=request.caption,
            hashtags=','.join(request.hashtags),
            status="posted",
            publish_id=result.get('publish_id', '')
        )
        self.session.add(post)
        await self.session.commit()
        await self.session.refresh(post)
        
        return PostResponse(
            status="success",
            message="Posted to TikTok successfully",
            post_id=post.post_id,
            publish_id=result.get('publish_id', ''),
            posted_at=post.created_at
        )
    
    async def get_user_posts(self, user_id: int) -> dict:
        """Get all posts for a user"""
        
        stmt = select(Post).where(
            Post.user_id == user_id
        ).order_by(Post.created_at.desc())
        
        result = await self.session.execute(stmt)
        posts = result.scalars().all()
        
        return {
            "posts": [
                {
                    "post_id": p.post_id,
                    "platform": p.platform,
                    "video_url": p.video_url,
                    "caption": p.caption,
                    "hashtags": p.hashtags.split(',') if p.hashtags else [],
                    "status": p.status,
                    "publish_id": p.publish_id,
                    "created_at": p.created_at
                }
                for p in posts
            ],
            "count": len(posts)
        }
