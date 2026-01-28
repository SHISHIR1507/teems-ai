"""
APScheduler service for background tasks
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import pytz
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.core import database as db_module
from app.services.db_helpers import (
    get_user_settings,
    get_upcoming_calendar_events
)
from app.services.google_calendar_service import google_calendar_service
from app.services.encryption_service import encryption_service
from app.orchestrator.meeting_orchestrator import sync_and_detect_meetings, auto_join_meeting
from app.services.nylas_service import nylas_service
from app.services.timezone_service import timezone_service
from app.services.notification_service import (
    notify_meeting_join_started,
    notify_meeting_join_completed,
    notify_meeting_join_failed
)

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def sync_calendar_for_user(tenant_id: str, user_id: str):
    """Sync calendar for a specific user"""
    try:
        if db_module.async_session_maker is None:
            db_module.init_engine()
        async with db_module.async_session_maker() as session:
            # Get user settings
            settings = await get_user_settings(session, tenant_id, user_id)
            if not settings or not settings.google_calendar_enabled:
                return
            
            if not settings.google_oauth_token or not settings.google_oauth_refresh_token:
                return
            
            # Get credentials
            credentials = google_calendar_service.get_credentials_from_encrypted(
                settings.google_oauth_token,
                settings.google_oauth_refresh_token
            )
            
            if not credentials:
                logger.warning(f"Failed to get credentials for user {user_id}")
                return
            
            # Sync events
            time_min = datetime.now(pytz.UTC)
            time_max = time_min + timedelta(days=7)
            
            events = google_calendar_service.sync_calendar_events(
                credentials,
                time_min=time_min,
                time_max=time_max
            )
            
            logger.info(f"Synced {len(events)} events for user {user_id}")
            
            # Use orchestrator to process sync (runs in thread pool)
            import asyncio
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                sync_and_detect_meetings,
                tenant_id,
                user_id,
                None  # Let orchestrator create its own session
            )
            
    except Exception as e:
        logger.error(f"Error syncing calendar for user {user_id}: {e}", exc_info=True)


async def check_and_join_meetings():
    """Check for upcoming meetings and join them"""
    try:
        if db_module.async_session_maker is None:
            db_module.init_engine()
        async with db_module.async_session_maker() as session:
            # Get all users with auto-join enabled
            from app.models.call import UserSettings
            from sqlalchemy import select
            
            result = await session.execute(
                select(UserSettings).where(
                    UserSettings.auto_join_enabled == True,
                    UserSettings.google_calendar_enabled == True
                )
            )
            users = result.scalars().all()
            
            now = datetime.now(pytz.UTC)
            time_window = now + timedelta(minutes=5)  # Check next 5 minutes
            
            for user_settings in users:
                try:
                    # Get upcoming events for this user
                    events = await get_upcoming_calendar_events(
                        session,
                        tenant_id=user_settings.tenant_id,
                        user_id=user_settings.user_id,
                        time_min=now,
                        time_max=time_window
                    )
                    
                    for event in events:
                        # Check if it's time to join (within 1 minute of start)
                        time_until_start = (event.start_time - now).total_seconds()
                        
                        if 0 <= time_until_start <= 60:  # Within 1 minute
                            if not event.auto_join_attempted:
                                logger.info(f"Auto-joining meeting: {event.title} for user {user_settings.user_id}")
                                
                                # Get call if exists for notification
                                call_id = event.call_id or "pending"
                                
                                # Notify join started
                                await notify_meeting_join_started(
                                    user_settings.tenant_id,
                                    call_id,
                                    event.title,
                                    event.start_time.isoformat() if event.start_time else ""
                                )
                                
                                # Use orchestrator to join (runs in thread pool)
                                import asyncio
                                loop = asyncio.get_event_loop()
                                result = await loop.run_in_executor(
                                    None,
                                    auto_join_meeting,
                                    event.id,
                                    user_settings.tenant_id,
                                    user_settings.user_id,
                                    None  # Let orchestrator create its own session
                                )
                                
                                if result.get("success"):
                                    logger.info(f"Successfully auto-joined meeting: {event.title}")
                                    # Get updated call_id from result if available
                                    try:
                                        import json
                                        message = result.get("message", "")
                                        if "call_id" in message.lower():
                                            import re
                                            match = re.search(r'call[_\s]*id[:\s]*["\']?([a-zA-Z0-9\-]+)', message, re.IGNORECASE)
                                            if match:
                                                call_id = match.group(1)
                                    except:
                                        pass
                                    
                                    # Extract notetaker_id
                                    notetaker_id = ""
                                    try:
                                        import json
                                        message = result.get("message", "")
                                        if "notetaker_id" in message.lower():
                                            import re
                                            match = re.search(r'notetaker[_\s]*id[:\s]*["\']?([a-zA-Z0-9\-]+)', message, re.IGNORECASE)
                                            if match:
                                                notetaker_id = match.group(1)
                                    except:
                                        pass
                                    
                                    await notify_meeting_join_completed(
                                        user_settings.tenant_id,
                                        call_id,
                                        notetaker_id,
                                        event.title
                                    )
                                else:
                                    logger.error(f"Failed to auto-join meeting: {result.get('message')}")
                                    await notify_meeting_join_failed(
                                        user_settings.tenant_id,
                                        call_id,
                                        result.get('message', 'Unknown error')
                                    )
                
                except Exception as e:
                    logger.error(f"Error processing user {user_settings.user_id}: {e}", exc_info=True)
    
    except Exception as e:
        logger.error(f"Error in check_and_join_meetings: {e}", exc_info=True)


async def refresh_oauth_tokens():
    """Refresh Google OAuth tokens daily"""
    try:
        if db_module.async_session_maker is None:
            db_module.init_engine()
        async with db_module.async_session_maker() as session:
            from app.models.call import UserSettings
            from sqlalchemy import select
            
            result = await session.execute(
                select(UserSettings).where(
                    UserSettings.google_calendar_enabled == True,
                    UserSettings.google_oauth_token.isnot(None)
                )
            )
            users = result.scalars().all()
            
            for user_settings in users:
                try:
                    credentials = google_calendar_service.get_credentials_from_encrypted(
                        user_settings.google_oauth_token,
                        user_settings.google_oauth_refresh_token
                    )
                    
                    if credentials:
                        # Refresh if needed
                        refreshed = google_calendar_service.refresh_credentials(credentials)
                        if refreshed:
                            # Re-encrypt and save
                            encrypted = google_calendar_service.encrypt_credentials(refreshed)
                            from app.services.db_helpers import update_user_settings
                            await update_user_settings(
                                session,
                                user_settings.tenant_id,
                                user_settings.user_id,
                                google_oauth_token=encrypted["encrypted_token"],
                                google_oauth_refresh_token=encrypted["encrypted_refresh_token"]
                            )
                            await session.commit()
                            logger.info(f"Refreshed tokens for user {user_settings.user_id}")
                
                except Exception as e:
                    logger.error(f"Error refreshing tokens for user {user_settings.user_id}: {e}")
    
    except Exception as e:
        logger.error(f"Error in refresh_oauth_tokens: {e}", exc_info=True)


def start_scheduler():
    """Start the background scheduler"""
    try:
        db_module.init_engine()  # Ensure database is initialized
        
        # Calendar sync: every 15 minutes
        scheduler.add_job(
            sync_calendar_for_all_users,
            trigger=IntervalTrigger(minutes=15),
            id='calendar_sync',
            replace_existing=True
        )
        
        # Auto-join check: every 1 minute
        scheduler.add_job(
            check_and_join_meetings,
            trigger=IntervalTrigger(minutes=1),
            id='auto_join_check',
            replace_existing=True
        )
        
        # Token refresh: daily at 2 AM UTC
        scheduler.add_job(
            refresh_oauth_tokens,
            trigger=CronTrigger(hour=2, minute=0, timezone=pytz.UTC),
            id='token_refresh',
            replace_existing=True
        )
        
        scheduler.start()
        logger.info("✅ Background scheduler started")
    
    except Exception as e:
        logger.error(f"Error starting scheduler: {e}", exc_info=True)


async def sync_calendar_for_all_users():
    """Sync calendar for all users with calendar enabled"""
    try:
        if db_module.async_session_maker is None:
            db_module.init_engine()
        async with db_module.async_session_maker() as session:
            from app.models.call import UserSettings
            from sqlalchemy import select
            
            result = await session.execute(
                select(UserSettings).where(
                    UserSettings.google_calendar_enabled == True
                )
            )
            users = result.scalars().all()
            
            for user_settings in users:
                await sync_calendar_for_user(
                    user_settings.tenant_id,
                    user_settings.user_id
                )
    
    except Exception as e:
        logger.error(f"Error in sync_calendar_for_all_users: {e}", exc_info=True)


def stop_scheduler():
    """Stop the background scheduler"""
    try:
        scheduler.shutdown()
        logger.info("Background scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}", exc_info=True)
