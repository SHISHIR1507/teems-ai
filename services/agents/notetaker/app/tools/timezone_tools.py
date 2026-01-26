"""
CrewAI Tools for timezone operations
"""
from crewai.tools import tool
from datetime import datetime
from app.services.timezone_service import timezone_service
from app.tools.async_helper import run_async
import pytz


@tool
def get_user_timezone(tenant_id: str, user_id: str, db_session=None) -> str:
    """
    Get user's timezone setting.
    
    Args:
        tenant_id: Tenant ID
        user_id: User ID
        db_session: Database session
    
    Returns:
        Timezone string (e.g., "America/New_York")
    
    IMPORTANT: Always use this tool to get real timezone. Never assume or make up timezones.
    """
    from app.services.db_helpers import get_or_create_user_settings
    
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
            return settings.timezone
        finally:
            if close_session and loop:
                try:
                    loop.run_until_complete(db_session.close())
                    loop.close()
                except:
                    pass
    except Exception as e:
        return "UTC"  # Default fallback


@tool
def convert_timezone(dt_str: str, from_tz: str, to_tz: str) -> str:
    """
    Convert datetime between timezones.
    
    Args:
        dt_str: ISO format datetime string
        from_tz: Source timezone
        to_tz: Target timezone
    
    Returns:
        Converted datetime as ISO string
    
    IMPORTANT: Always use this tool for timezone conversions. Never calculate manually.
    """
    try:
        # Parse datetime
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        
        # Convert
        if from_tz.lower() != 'utc':
            dt = timezone_service.convert_to_utc(dt, from_tz)
        
        if to_tz.lower() != 'utc':
            dt = timezone_service.convert_from_utc(dt, to_tz)
        
        return dt.isoformat()
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def calculate_join_time(event_start_time: str, user_timezone: str) -> str:
    """
    Calculate the exact join time for a meeting (same as start time).
    
    Args:
        event_start_time: Event start time (ISO format, UTC)
        user_timezone: User's timezone
    
    Returns:
        Join time as ISO string (UTC) for Nylas API
    
    IMPORTANT: Join time should be exactly the start time. Never join before or after.
    """
    try:
        # Parse event start time (assumed UTC)
        dt = datetime.fromisoformat(event_start_time.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        
        # Return as ISO string for Nylas (UTC)
        return timezone_service.format_datetime_for_nylas(dt)
    except Exception as e:
        return f"Error: {str(e)}"
