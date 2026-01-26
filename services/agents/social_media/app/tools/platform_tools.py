"""
CrewAI Tools for Multi-Platform Operations
These tools work across all social media platforms.
"""
from crewai.tools import tool
import asyncio
from app.services.social_media_service import SocialMediaService
from app.services.db_helpers import run_with_db_session


@tool
def get_user_posts(tenant_id: str, platform: str = "all", limit: int = 10) -> str:
    """
    Get posting history across all platforms or a specific platform.
    
    Args:
        tenant_id: Tenant ID from authenticated user
        platform: Platform to get posts from ("tiktok", "facebook", or "all")
        limit: Number of posts per platform (default 10)
    
    Returns:
        Formatted list of posts across platforms
    """
    try:
        async def _get_posts(session):
            service = SocialMediaService(session, tenant_id)
            return await service.get_all_posts_async(platform=platform, limit=limit)
        
        result = asyncio.run(run_with_db_session(_get_posts))
        posts_by_platform = result.get("posts_by_platform", {})
        
        if not posts_by_platform:
            return "📊 No posts found. Start posting to see your history here!"
        
        output = []
        for platform_name, posts in posts_by_platform.items():
            if not posts:
                continue
            output.append(f"\n📱 {platform_name.upper()} Posts ({len(posts)}):")
            for post in posts:
                hashtags = post.get("hashtags", [])
                hashtag_text = ' '.join(['#' + tag for tag in hashtags]) if hashtags else ''
                output.append(
                    f"  • {post.get('caption', 'No caption')}"
                    + (f" {hashtag_text}" if hashtag_text else "")
                    + f"\n    Status: {post.get('status', 'unknown')} | Posted: {post.get('created_at', 'unknown')}"
                )
        return "\n".join(output) if output else "📊 No posts found."
    except Exception as e:
        return f"❌ Failed to get posts: {str(e)}"


@tool
def get_connected_platforms(tenant_id: str) -> str:
    """
    Get list of platforms the user has connected (has tokens for).
    
    Args:
        tenant_id: Tenant ID from authenticated user
    
    Returns:
        List of connected platforms
    """
    try:
        async def _get_platforms(session):
            service = SocialMediaService(session, tenant_id)
            return await service.get_connected_platforms_async()
        
        result = asyncio.run(run_with_db_session(_get_platforms))
        platforms = result.get("platforms", [])
        
        if not platforms:
            return "❌ No platforms connected. Connect your accounts via OAuth to start posting!"
        
        platform_list = "\n".join([f"  ✅ {p.capitalize()}" for p in platforms])
        return f"📱 Connected Platforms:\n{platform_list}"
    except Exception as e:
        return f"❌ Failed to get connected platforms: {str(e)}"
