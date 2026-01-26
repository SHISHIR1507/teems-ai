"""
CrewAI Tools for Facebook Posting
These tools are called by CrewAI agents and use async services via run_with_db_session.
"""
from crewai.tools import tool
from typing import Optional
import asyncio
from app.services.facebook_service import FacebookService
from app.services.db_helpers import run_with_db_session


@tool
def post_to_facebook(
    user_id: str,
    tenant_id: str,
    video_url: str,
    caption: str,
    page_id: Optional[str] = None
) -> str:
    """
    Post a video to Facebook using Graph API.
    
    Use this tool when the user wants to post a video to Facebook.
    
    Args:
        user_id: Auth0 user ID (sub)
        tenant_id: Tenant ID from authenticated user
        video_url: Publicly accessible video URL
        caption: Video caption/description
        page_id: Optional Facebook Page ID (if posting to a page instead of personal profile)
    
    Returns:
        Success message with Facebook post ID
    """
    try:
        async def _post(session):
            service = FacebookService(session, tenant_id)
            return await service.post_video_async(
                user_id=user_id,
                video_url=video_url,
                caption=caption,
                page_id=page_id
            )
        
        result = asyncio.run(run_with_db_session(_post))
        
        if result.get("status") == "success":
            post_id = result.get("post_id", "N/A")
            target = f"Page {page_id}" if page_id else "your profile"
            return f"""✅ Successfully posted to Facebook!

📝 Caption: {caption}
📍 Target: {target}
🆔 Post ID: {post_id}

Your video is now live on Facebook!"""
        else:
            error_msg = result.get("error", "Unknown error")
            return f"❌ Failed to post to Facebook: {error_msg}"
    except Exception as e:
        return f"❌ Failed to post to Facebook: {str(e)}"


@tool
def get_facebook_posts(tenant_id: str, limit: int = 10) -> str:
    """
    Get Facebook posting history for the tenant.
    
    Args:
        tenant_id: Tenant ID from authenticated user
        limit: Number of posts to retrieve (default 10)
    
    Returns:
        Formatted list of posts
    """
    try:
        async def _get_posts(session):
            service = FacebookService(session, tenant_id)
            return await service.get_posts_async(platform="facebook", limit=limit)
        
        result = asyncio.run(run_with_db_session(_get_posts))
        posts = result.get("posts", [])
        
        if not posts:
            return "📊 No Facebook posts found. Start posting to see your history here!"
        
        post_list = []
        for post in posts:
            post_list.append(
                f"• {post.get('caption', 'No caption')}\n"
                f"  Status: {post.get('status', 'unknown')}\n"
                f"  Posted: {post.get('created_at', 'unknown')}"
            )
        return f"📊 Your Facebook Posts ({len(posts)}):\n\n" + "\n\n".join(post_list)
    except Exception as e:
        return f"❌ Failed to get Facebook posts: {str(e)}"
