"""
CrewAI Tools for Google Calendar operations
"""
from crewai.tools import tool
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import pytz
from app.services.google_calendar_service import google_calendar_service
from app.services.timezone_service import timezone_service
from app.services.db_helpers import (
    get_user_settings,
    get_or_create_user_settings,
    update_user_settings,
    get_upcoming_calendar_events,
    create_calendar_event,
    get_calendar_event_by_google_id,
    update_calendar_event
)
from app.services.encryption_service import encryption_service
from app.tools.async_helper import run_async
import logging

logger = logging.getLogger(__name__)


@tool
def sync_google_calendar(tenant_id: str, user_id: str, db_session=None) -> str:
    """
    Sync calendar events from Google Calendar for a user.
    
    This tool:
    1. Gets user's Google Calendar credentials
    2. Fetches events from Google Calendar
    3. Creates/updates CalendarEvent records in database
    4. Extracts meeting links from events
    
    Args:
        tenant_id: Tenant ID
        user_id: User ID
        db_session: Optional database session (creates new if None)
    
    Returns:
        JSON string with sync results: {"synced": count, "events": [...]}
    
    IMPORTANT: Always use this tool to get real calendar data. Never make up events.
    """
    try:
        # Create session if not provided
        if db_session is None:
            from app.tools.async_helper import get_db_session_sync
            db_session, loop = get_db_session_sync()
            close_session = True
        else:
            close_session = False
            loop = None
        
        try:
            # Get user settings (async call in sync context)
            settings = run_async(get_user_settings(db_session, tenant_id, user_id))
        if not settings or not settings.google_calendar_enabled:
            return '{"error": "Google Calendar not enabled for user", "synced": 0}'
        
        if not settings.google_oauth_token or not settings.google_oauth_refresh_token:
            return '{"error": "Google OAuth tokens not found", "synced": 0}'
        
        # Get credentials from encrypted tokens
        credentials = google_calendar_service.get_credentials_from_encrypted(
            settings.google_oauth_token,
            settings.google_oauth_refresh_token
        )
        
        if not credentials:
            return '{"error": "Failed to get Google credentials", "synced": 0}'
        
        # Sync events (next 7 days)
        time_min = datetime.now(pytz.UTC)
        time_max = time_min + timedelta(days=7)
        
        google_events = google_calendar_service.sync_calendar_events(
            credentials,
            time_min=time_min,
            time_max=time_max
        )
        
        synced_count = 0
        events_data = []
        
        for google_event in google_events:
            google_event_id = google_event.get('id')
            if not google_event_id:
                continue
            
            # Check if event already exists
            existing_event = run_async(get_calendar_event_by_google_id(
                db_session,
                google_event_id,
                tenant_id
            ))
            
            # Parse event times
            start_dict = google_event.get('start', {})
            end_dict = google_event.get('end', {})
            
            start_time = google_calendar_service.parse_event_datetime(start_dict)
            end_time = google_calendar_service.parse_event_datetime(end_dict)
            
            if not start_time or not end_time:
                continue
            
            # Extract meeting link
            meeting_link = google_calendar_service.extract_meeting_link_from_event(google_event)
            
            # Detect platform
            from app.services.meeting_detection_service import meeting_detection_service
            meeting_platform = None
            if meeting_link:
                meeting_platform = meeting_detection_service.detect_platform(meeting_link)
            
            title = google_event.get('summary', 'Untitled Event')
            description = google_event.get('description', '')
            
            if existing_event:
                # Update existing event
                run_async(update_calendar_event(
                    db_session,
                    existing_event.id,
                    tenant_id,
                    title=title,
                    description=description,
                    start_time=start_time,
                    end_time=end_time,
                    meeting_link=meeting_link,
                    meeting_platform=meeting_platform
                ))
            else:
                # Create new event
                run_async(create_calendar_event(
                    db_session,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    google_event_id=google_event_id,
                    title=title,
                    description=description,
                    start_time=start_time,
                    end_time=end_time,
                    meeting_link=meeting_link,
                    meeting_platform=meeting_platform
                ))
            
            synced_count += 1
            events_data.append({
                "id": google_event_id,
                "title": title,
                "start_time": start_time.isoformat(),
                "has_meeting_link": meeting_link is not None
            })
        
        # Update last sync time
        run_async(update_user_settings(
            db_session,
            tenant_id,
            user_id,
            last_calendar_sync=datetime.utcnow()
        ))
        
        run_async(db_session.commit())
        
            import json
            return json.dumps({
                "synced": synced_count,
                "events": events_data,
                "message": f"Successfully synced {synced_count} calendar events"
            })
        finally:
            if close_session and loop:
                try:
                    loop.run_until_complete(db_session.close())
                    loop.close()
                except:
                    pass
    
    except Exception as e:
        logger.error(f"Error syncing calendar: {e}", exc_info=True)
        return f'{{"error": "{str(e)}", "synced": 0}}'


@tool
def get_upcoming_meetings(tenant_id: str, user_id: str, db_session=None, hours_ahead: int = 24) -> str:
    """
    Get upcoming meetings that can be auto-joined.
    
    Args:
        tenant_id: Tenant ID
        user_id: User ID
        db_session: Database session
        hours_ahead: How many hours ahead to look (default: 24)
    
    Returns:
        JSON string with upcoming meetings
    
    IMPORTANT: Always use this tool to get real meeting data. Never make up meetings.
    """
    try:
        # Create session if not provided
        if db_session is None:
            from app.tools.async_helper import get_db_session_sync
            db_session, loop = get_db_session_sync()
            close_session = True
        else:
            close_session = False
            loop = None
        
        try:
            time_min = datetime.now(pytz.UTC)
            time_max = time_min + timedelta(hours=hours_ahead)
            
            events = run_async(get_upcoming_calendar_events(
                db_session,
                tenant_id=tenant_id,
                user_id=user_id,
                time_min=time_min,
                time_max=time_max
            ))
        
        meetings = []
        for event in events:
            meetings.append({
                "id": event.id,
                "title": event.title,
                "start_time": event.start_time.isoformat(),
                "meeting_link": event.meeting_link,
                "platform": event.meeting_platform,
                "status": event.status,
                "already_joined": event.status in ["joined", "completed"]
            })
        
            import json
            return json.dumps({
                "meetings": meetings,
                "count": len(meetings)
            })
        finally:
            if close_session and loop:
                try:
                    loop.run_until_complete(db_session.close())
                    loop.close()
                except:
                    pass
    
    except Exception as e:
        logger.error(f"Error getting upcoming meetings: {e}", exc_info=True)
        return '{"error": "' + str(e) + '", "meetings": []}'


@tool
def get_calendar_settings(tenant_id: str, user_id: str, db_session=None) -> str:
    """
    Get user's calendar settings including timezone and auto-join status.
    
    Args:
        tenant_id: Tenant ID
        user_id: User ID
        db_session: Database session
    
    Returns:
        JSON string with settings
    
    IMPORTANT: Always use this tool to get real settings. Never make up values.
    """
    try:
        # Create session if not provided
        if db_session is None:
            from app.tools.async_helper import get_db_session_sync
            db_session, loop = get_db_session_sync()
            close_session = True
        else:
            close_session = False
            loop = None
        
        try:
            settings = run_async(get_or_create_user_settings(db_session, tenant_id, user_id))
            
            import json
            return json.dumps({
                "timezone": settings.timezone,
                "google_calendar_enabled": settings.google_calendar_enabled,
                "auto_join_enabled": settings.auto_join_enabled,
                "last_calendar_sync": settings.last_calendar_sync.isoformat() if settings.last_calendar_sync else None
            })
        finally:
            if close_session and loop:
                try:
                    loop.run_until_complete(db_session.close())
                    loop.close()
                except:
                    pass
    
    except Exception as e:
        logger.error(f"Error getting calendar settings: {e}", exc_info=True)
        return '{"error": "' + str(e) + '"}'


@tool
def update_timezone(tenant_id: str, user_id: str, timezone: str, db_session=None) -> str:
    """
    Update user's timezone setting.
    
    Args:
        tenant_id: Tenant ID
        user_id: User ID
        timezone: Timezone string (e.g., "America/New_York")
        db_session: Database session
    
    Returns:
        Success message or error
    
    IMPORTANT: Validate timezone before updating. Use timezone_service.validate_timezone().
    """
    try:
        # Create session if not provided
        if db_session is None:
            from app.tools.async_helper import get_db_session_sync
            db_session, loop = get_db_session_sync()
            close_session = True
        else:
            close_session = False
            loop = None
        
        try:
            # Validate timezone
            if not timezone_service.validate_timezone(timezone):
                return f'{{"error": "Invalid timezone: {timezone}"}}'
            
            run_async(update_user_settings(
                db_session,
                tenant_id,
                user_id,
                timezone=timezone
            ))
            
            run_async(db_session.commit())
            
            return f'{{"success": true, "message": "Timezone updated to {timezone}"}}'
        finally:
            if close_session and loop:
                try:
                    loop.run_until_complete(db_session.close())
                    loop.close()
                except:
                    pass
    
    except Exception as e:
        logger.error(f"Error updating timezone: {e}", exc_info=True)
        return f'{{"error": "{str(e)}"}}'
