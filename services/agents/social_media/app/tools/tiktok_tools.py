"""
CrewAI Tools for TikTok Posting
These tools are called by CrewAI agents and use async services via run_with_db_session.
"""
from crewai.tools import tool
from typing import List
import asyncio
from app.services.tiktok_service import TikTokService
from app.services.db_helpers import run_with_db_session


@tool
def post_to_tiktok(user_id: str, tenant_id: str, video_url: str, caption: str, hashtags: List[str] = None) -> str:
    """
    Post a video to TikTok using FILE_UPLOAD method.
    
    Use this tool when the user wants to post a video to TikTok.
    
    Args:
        user_id: Auth0 user ID (sub)
        tenant_id: Tenant ID from authenticated user
        video_url: Publicly accessible video URL (must be direct link to MP4)
        caption: Video caption/description
        hashtags: List of hashtags (without # symbol), optional
    
    Returns:
        Success message with TikTok publish ID
    """
    if hashtags is None:
        hashtags = []
    
    try:
        async def _post(session):
            service = TikTokService(session, tenant_id)
            return await service.post_video_async(
                user_id=user_id,
                video_url=video_url,
                caption=caption,
                hashtags=hashtags
            )
        
        result = asyncio.run(run_with_db_session(_post))
        
        if result.get("status") == "success":
            publish_id = result.get("publish_id", "N/A")
            hashtag_text = ' '.join(['#' + tag for tag in hashtags]) if hashtags else 'none'
            return f"""✅ Successfully posted to TikTok!

📝 Caption: {caption}
🏷️ Hashtags: {hashtag_text}
🆔 Publish ID: {publish_id}

Your video is now live on TikTok (private - only you can see it)!"""
        else:
            error_msg = result.get("error", "Unknown error")
            return f"❌ Failed to post to TikTok: {error_msg}"
    except Exception as e:
        return f"❌ Failed to post to TikTok: {str(e)}"


@tool
def refresh_tiktok_token(tenant_id: str) -> str:
    """
    Refresh TikTok access token using refresh token.
    
    Use this tool when TikTok token has expired.
    
    Args:
        tenant_id: Tenant ID from authenticated user
    
    Returns:
        Success message
    """
    try:
        async def _refresh(session):
            service = TikTokService(session, tenant_id)
            return await service.refresh_token_async()
        
        result = asyncio.run(run_with_db_session(_refresh))
        if result.get("status") == "success":
            return "✅ TikTok token refreshed successfully!"
        else:
            error_msg = result.get("error", "Unknown error")
            return f"❌ Failed to refresh TikTok token: {error_msg}"
    except Exception as e:
        return f"❌ Failed to refresh TikTok token: {str(e)}"


@tool
def get_tiktok_posts(tenant_id: str, limit: int = 10) -> str:
    """
    Get TikTok posting history for the tenant.
    
    Args:
        tenant_id: Tenant ID from authenticated user
        limit: Number of posts to retrieve (default 10)
    
    Returns:
        Formatted list of posts
    """
    try:
        async def _get_posts(session):
            service = TikTokService(session, tenant_id)
            return await service.get_posts_async(platform="tiktok", limit=limit)
        
        result = asyncio.run(run_with_db_session(_get_posts))
        posts = result.get("posts", [])
        
        if not posts:
            return "📊 No TikTok posts found. Start posting to see your history here!"
        
        post_list = []
        for post in posts:
            hashtags = post.get("hashtags", [])
            hashtag_text = ' '.join(['#' + tag for tag in hashtags]) if hashtags else 'none'
            post_list.append(
                f"• {post.get('caption', 'No caption')}\n"
                f"  Hashtags: {hashtag_text}\n"
                f"  Status: {post.get('status', 'unknown')}\n"
                f"  Posted: {post.get('created_at', 'unknown')}"
            )
        return f"📊 Your TikTok Posts ({len(posts)}):\n\n" + "\n\n".join(post_list)
    except Exception as e:
        return f"❌ Failed to get TikTok posts: {str(e)}"
