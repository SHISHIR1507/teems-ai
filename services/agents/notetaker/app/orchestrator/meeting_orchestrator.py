"""
Meeting Orchestrator
Coordinates multi-agent workflows for calendar sync and auto-join
"""
from crewai import Task, Crew
from app.agents.calendar_sync_agent import create_calendar_sync_agent
from app.agents.meeting_detection_agent import create_meeting_detection_agent
from app.agents.meeting_join_agent import create_meeting_join_agent
from typing import Optional, Dict, Any
import concurrent.futures
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import async_session_maker, init_engine

logger = logging.getLogger(__name__)

# Thread pool for running CrewAI without blocking
executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)


def sync_and_detect_meetings(
    tenant_id: str,
    user_id: str,
    db_session: Optional[AsyncSession] = None
) -> Dict[str, Any]:
    """
    Orchestrate calendar sync and meeting detection workflow
    
    This uses 2-agent sequential workflow:
    1. Calendar Sync Agent - syncs Google Calendar events
    2. Meeting Detection Agent - identifies meetings to join
    
    Args:
        tenant_id: Tenant ID
        user_id: User ID
        db_session: Optional database session (creates new if None)
    
    Returns:
        Dict with sync results and detected meetings
    """
    sync_agent = create_calendar_sync_agent()
    detection_agent = create_meeting_detection_agent()
    
    # Create session for tools if not provided
    session_context = None
    if db_session is None:
        if async_session_maker is None:
            init_engine()
        # Tools will create their own sessions via async_helper
    
    # Task 1: Sync calendar
    task1 = Task(
        description=f"""Sync Google Calendar events for user.
        
        Tenant ID: {tenant_id}
        User ID: {user_id}
        
        Use sync_google_calendar tool with tenant_id={tenant_id}, user_id={user_id}, db_session=None.
        The tool will create its own database session.
        
        Steps:
        1. Get user's Google Calendar credentials
        2. Fetch events from Google Calendar (next 7 days)
        3. Create/update CalendarEvent records in database
        4. Extract meeting links from events
        
        Report the number of events synced and how many have meeting links.
        Always use tools to get real data - never make up events.""",
        expected_output="JSON string with sync results: synced count and events list",
        agent=sync_agent,
        human_input=False
    )
    
    # Task 2: Detect meetings (depends on task1)
    task2 = Task(
        description=f"""Identify meetings that can be auto-joined.
        
        Tenant ID: {tenant_id}
        User ID: {user_id}
        
        Use get_upcoming_meetings tool with tenant_id={tenant_id}, user_id={user_id}, db_session=None.
        The tool will create its own database session.
        
        Steps:
        1. Get upcoming calendar events with meeting links
        2. Filter for events that haven't been joined yet
        3. Detect meeting platform for each event
        4. Calculate exact join time for each meeting
        
        Report which meetings are ready to be joined.
        Always use tools to get real data - never make up meetings.""",
        expected_output="JSON string with upcoming meetings that can be joined",
        agent=detection_agent,
        context=[task1],
        human_input=False
    )
    
    crew = Crew(
        agents=[sync_agent, detection_agent],
        tasks=[task1, task2],
        process="sequential",
        verbose=True,
        full_output=False
    )
    
    try:
        future = executor.submit(crew.kickoff)
        result = future.result(timeout=180)
        result_str = str(result)
        
        logger.info(f"Calendar sync and detection completed: {result_str}")
        
        return {
            "success": True,
            "message": result_str,
            "tenant_id": tenant_id,
            "user_id": user_id
        }
    except concurrent.futures.TimeoutError:
        logger.error("Calendar sync timed out")
        return {
            "success": False,
            "message": "Calendar sync timed out. Please try again.",
            "tenant_id": tenant_id,
            "user_id": user_id
        }
    except Exception as e:
        logger.error(f"Error in calendar sync workflow: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "tenant_id": tenant_id,
            "user_id": user_id
        }


def auto_join_meeting(
    calendar_event_id: str,
    tenant_id: str,
    user_id: str,
    db_session: Optional[AsyncSession] = None
) -> Dict[str, Any]:
    """
    Orchestrate meeting join workflow
    
    This uses the Meeting Join Agent to:
    1. Validate meeting link
    2. Join meeting via Nylas API
    3. Update database records
    
    Args:
        calendar_event_id: Calendar event ID
        tenant_id: Tenant ID
        user_id: User ID
        db_session: Optional database session (creates new if None)
    
    Returns:
        Dict with join results
    """
    join_agent = create_meeting_join_agent()
    
    task = Task(
        description=f"""Join a meeting via Nylas API.
        
        Calendar Event ID: {calendar_event_id}
        Tenant ID: {tenant_id}
        User ID: {user_id}
        
        Use join_meeting_via_nylas tool with calendar_event_id={calendar_event_id}, tenant_id={tenant_id}, user_id={user_id}, db_session=None.
        The tool will create its own database session.
        
        Steps:
        1. Get calendar event details
        2. Validate meeting link
        3. Join meeting via Nylas API at exact start time
        4. Update event and call records with notetaker ID
        
        Report the actual join result from Nylas API.
        Always use tools to join - never report success without API confirmation.""",
        expected_output="JSON string with join result: success, notetaker_id, call_id",
        agent=join_agent,
        human_input=False
    )
    
    crew = Crew(
        agents=[join_agent],
        tasks=[task],
        verbose=True,
        full_output=False
    )
    
    try:
        future = executor.submit(crew.kickoff)
        result = future.result(timeout=120)
        result_str = str(result)
        
        logger.info(f"Meeting join completed: {result_str}")
        
        return {
            "success": True,
            "message": result_str,
            "calendar_event_id": calendar_event_id,
            "tenant_id": tenant_id
        }
    except concurrent.futures.TimeoutError:
        logger.error("Meeting join timed out")
        return {
            "success": False,
            "message": "Meeting join timed out. Please try again.",
            "calendar_event_id": calendar_event_id
        }
    except Exception as e:
        logger.error(f"Error in meeting join workflow: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "calendar_event_id": calendar_event_id
        }


def process_joined_meeting(
    call_id: str,
    tenant_id: str
) -> Dict[str, Any]:
    """
    Continue processing for a joined meeting
    
    This is called after a meeting is joined to continue with the existing flow:
    - Wait for Nylas webhook with transcript
    - Process transcript for RAG
    - Enable Q&A functionality
    
    Note: This is mostly handled by existing webhook processing,
    but this function can be used to trigger additional processing if needed.
    
    Args:
        call_id: Call ID
        tenant_id: Tenant ID
    
    Returns:
        Dict with processing status
    """
    # The existing webhook processing handles this
    # This function is a placeholder for future enhancements
    return {
        "success": True,
        "message": "Meeting processing will continue via webhook",
        "call_id": call_id
    }
