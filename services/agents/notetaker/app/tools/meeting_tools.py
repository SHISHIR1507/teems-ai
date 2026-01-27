"""
CrewAI Tools for meeting operations
"""
from crewai.tools import tool
from typing import Dict, Any
from datetime import datetime
import pytz
import json
import logging
from app.services.nylas_service import nylas_service
from app.services.meeting_detection_service import meeting_detection_service
from app.services.timezone_service import timezone_service
from app.services.db_helpers import (
    get_calendar_event,
    update_calendar_event,
    create_call,
    update_call
)
from app.tools.async_helper import run_async

logger = logging.getLogger(__name__)


@tool
def detect_meeting_platform(meeting_link: str) -> str:
    """
    Detect meeting platform from a meeting link.
    
    Args:
        meeting_link: Meeting URL
    
    Returns:
        Platform name (zoom, teams, google_meet, etc.) or "unknown"
    
    IMPORTANT: Always use this tool to detect platform. Never guess.
    """
    try:
        platform = meeting_detection_service.detect_platform(meeting_link)
        return platform or "unknown"
    except Exception as e:
        logger.error(f"Error detecting platform: {e}")
        return "unknown"


@tool
def join_meeting_via_nylas(
    calendar_event_id: str,
    tenant_id: str,
    user_id: str,
    db_session=None
) -> str:
    """
    Join a meeting via Nylas API at the scheduled time.
    
    This tool:
    1. Gets calendar event details
    2. Validates meeting link
    3. Calls Nylas API to join meeting
    4. Updates event and call records
    
    Args:
        calendar_event_id: Calendar event ID
        tenant_id: Tenant ID
        user_id: User ID
        db_session: Optional database session (creates new if None)
    
    Returns:
        JSON string with join result: {"success": true, "notetaker_id": "...", "message": "..."}
    
    IMPORTANT: Only call this tool when you have verified the meeting link and time.
    Never join meetings without proper validation.
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
            # Get calendar event
            event = run_async(get_calendar_event(db_session, calendar_event_id, tenant_id))
            if not event:
                return '{"error": "Calendar event not found", "success": false}'
            
            if not event.meeting_link:
                return '{"error": "No meeting link in calendar event", "success": false}'
            
            # Check if already joined
            if event.status in ["joined", "completed"]:
                return f'{{"success": true, "message": "Meeting already joined", "notetaker_id": "{event.nylas_notetaker_id}"}}'
            
            # Validate meeting link
            validation = meeting_detection_service.validate_meeting_link(event.meeting_link)
            if not validation["is_valid"]:
                error_msg = validation.get("error")
                return f'{{"error": "Invalid meeting link: {error_msg}", "success": false}}'
            
            # Format join time (exactly at start time)
            join_time_iso = timezone_service.format_datetime_for_nylas(event.start_time)
            
            # Join via Nylas
            nylas_response = nylas_service.join_meeting(
                meeting_link=event.meeting_link,
                join_time=join_time_iso,
                name=event.title
            )
            
            # Extract notetaker ID
            notetaker_id = None
            if isinstance(nylas_response, dict):
                notetaker_id = nylas_response.get("data", {}).get("id")
            
            if not notetaker_id:
                return '{"error": "Failed to get notetaker ID from Nylas", "success": false}'
            
            # Create or update call record
            call = None
            if event.call_id:
                # Update existing call
                from app.services.db_helpers import get_call
                call = run_async(get_call(db_session, event.call_id, tenant_id))
            
            if not call:
                # Create new call
                call = run_async(create_call(
                    db_session,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    title=event.title,
                    meeting_link=event.meeting_link,
                    start_time=event.start_time,
                    calendar_event_id=calendar_event_id
                ))
            
            # Update call with Nylas meeting ID
            run_async(update_call(
                db_session,
                call.id,
                tenant_id,
                meeting_id=notetaker_id,
                auto_joined=True,
                join_attempted_at=datetime.utcnow(),
                status="processing"
            ))
            
            # Update calendar event
            run_async(update_calendar_event(
                db_session,
                calendar_event_id,
                tenant_id,
                call_id=call.id,
                nylas_notetaker_id=notetaker_id,
                status="joined",
                auto_join_attempted=True,
                join_attempted_at=datetime.utcnow()
            ))
            
            run_async(db_session.commit())
            
            return json.dumps({
                "success": True,
                "notetaker_id": notetaker_id,
                "call_id": call.id,
                "message": f"Successfully joined meeting: {event.title}"
            })
        finally:
            if close_session and loop:
                try:
                    loop.run_until_complete(db_session.close())
                    loop.close()
                except:
                    pass
    
    except Exception as e:
        logger.error(f"Error joining meeting: {e}", exc_info=True)
        return f'{{"error": "{str(e)}", "success": false}}'


@tool
def check_meeting_status(notetaker_id: str) -> str:
    """
    Check status of a Nylas notetaker instance.
    
    Args:
        notetaker_id: Nylas notetaker ID
    
    Returns:
        JSON string with status information
    
    IMPORTANT: Always use this tool to get real status. Never make up status.
    """
    try:
        status = nylas_service.get_notetaker_status(notetaker_id)
        
        if not status:
            return '{"error": "Failed to get notetaker status", "status": "unknown"}'
        
        return json.dumps(status)
    
    except Exception as e:
        logger.error(f"Error checking meeting status: {e}", exc_info=True)
        return f'{{"error": "{str(e)}", "status": "unknown"}}'


@tool
def get_notetaker_status(notetaker_id: str) -> str:
    """
    Get detailed status of a Nylas notetaker instance.
    
    This is an alias for check_meeting_status for consistency.
    
    Args:
        notetaker_id: Nylas notetaker ID
    
    Returns:
        JSON string with detailed status
    """
    return check_meeting_status(notetaker_id)
