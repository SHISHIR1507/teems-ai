"""
APScheduler service for processing scheduled posts
Runs background jobs to check and execute scheduled social media posts
"""
from datetime import datetime, timezone
import logging
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.database import init_engine, async_session_maker, Post
from app.services.tiktok_service import TikTokService
from app.services.realtime_notifier import (
    notify_posting_started,
    notify_posting_progress,
    notify_posting_completed,
    notify_posting_error,
)

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def process_scheduled_posts():
    """
    Background job: Check for scheduled posts that are ready to be published.
    Runs every minute to process posts where scheduled_at <= now() and status = 'scheduled'
    """
    try:
        if async_session_maker is None:
            init_engine()
        
        async with async_session_maker() as session:
            now = datetime.now(timezone.utc)
            
            # Find all scheduled posts that are ready to be published
            result = await session.execute(
                select(Post).where(
                    Post.status == "scheduled",
                    Post.scheduled_at <= now
                ).order_by(Post.scheduled_at.asc())
            )
            scheduled_posts = result.scalars().all()
            
            if not scheduled_posts:
                return
            
            logger.info(f"Processing {len(scheduled_posts)} scheduled post(s)")
            
            for post in scheduled_posts:
                try:
                    # Update status to processing
                    post.status = "processing"
                    await session.flush()
                    
                    # Notify posting started
                    await notify_posting_started(
                        post.tenant_id,
                        post.conversation_id or "",
                        post.platform,
                        post.video_url
                    )
                    
                    # Execute posting based on platform
                    # Use the client directly to avoid creating duplicate post records
                    if post.platform == "tiktok":
                        from app.services.tiktok_client import TikTokClient
                        from app.services.db_helpers import get_tenant_token
                        
                        token_record = await get_tenant_token(session, post.tenant_id, "tiktok")
                        if not token_record:
                            raise ValueError("No TikTok token found")
                        
                        client = TikTokClient()
                        api_result = client.post_video(
                            video_url=post.video_url,
                            caption=post.caption or "",
                            hashtags=post.hashtags.split(",") if post.hashtags else [],
                            access_token=token_record.access_token
                        )
                        
                        publish_id = api_result.get("publish_id")
                        if not publish_id:
                            raise ValueError("No publish_id returned from TikTok")
                        
                        # Update existing post record (don't create duplicate)
                        post.status = "posted"
                        post.publish_id = publish_id
                        post.extra = api_result
                        await session.flush()
                            
                    elif post.platform == "facebook":
                        from app.services.facebook_client import FacebookClient
                        from app.services.db_helpers import get_tenant_token
                        
                        token_record = await get_tenant_token(session, post.tenant_id, "facebook")
                        if not token_record:
                            raise ValueError("No Facebook token found")
                        
                        client = FacebookClient()
                        page_id = (post.extra or {}).get("page_id") or token_record.platform_user_id
                        api_result = client.post_video(
                            video_url=post.video_url,
                            caption=post.caption or "",
                            access_token=token_record.access_token,
                            page_id=page_id,
                            user_id=None if page_id else post.user_id
                        )
                        
                        post_id = api_result.get("post_id")
                        if not post_id:
                            raise ValueError("No post_id returned from Facebook")
                        
                        # Update existing post record (don't create duplicate)
                        post.status = "posted"
                        post.publish_id = post_id
                        if not post.extra:
                            post.extra = {}
                        post.extra.update(api_result)
                        await session.flush()
                    else:
                        raise ValueError(f"Unsupported platform: {post.platform}")
                    
                    # If we reach here, posting was successful (post already updated above)
                    # Notify completion
                    await notify_posting_completed(
                        post.tenant_id,
                        post.conversation_id or "",
                        post.platform,
                        post.id,
                        post.publish_id
                    )
                    
                    logger.info(f"✅ Scheduled post {post.id} published successfully to {post.platform}")
                    
                except Exception as e:
                    # Mark post as failed
                    post.status = "failed"
                    post.error = str(e)
                    await session.flush()
                    
                    # Notify error
                    await notify_posting_error(
                        post.tenant_id,
                        post.conversation_id or "",
                        post.platform,
                        str(e)
                    )
                    
                    logger.error(f"❌ Error processing scheduled post {post.id}: {e}", exc_info=True)
            
            # Commit all changes
            await session.commit()
            
    except Exception as e:
        logger.error(f"Error in process_scheduled_posts: {e}", exc_info=True)


def start_scheduler():
    """Start the background scheduler"""
    try:
        init_engine()  # Ensure database is initialized
        
        # Process scheduled posts: every 1 minute
        scheduler.add_job(
            process_scheduled_posts,
            trigger=IntervalTrigger(minutes=1),
            id='process_scheduled_posts',
            replace_existing=True
        )
        
        scheduler.start()
        logger.info("✅ Background scheduler started for scheduled posts")
    
    except Exception as e:
        logger.error(f"Error starting scheduler: {e}", exc_info=True)


def stop_scheduler():
    """Stop the background scheduler"""
    try:
        scheduler.shutdown()
        logger.info("Background scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}", exc_info=True)
