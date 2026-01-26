"""
Auto-join meeting endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.core.dependencies import get_db_session
from app.core.auth import AuthenticatedUser, require_tenant
from app.services.db_helpers import (
    get_calendar_event,
    get_upcoming_calendar_events
)
from app.orchestrator.meeting_orchestrator import auto_join_meeting
from datetime import datetime, timedelta
import pytz

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/v1/meetings/{call_id}/join", tags=["auto-join"])
async def manual_join_meeting(
    call_id: str,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Manually trigger meeting join for a call.
    
    This uses the CrewAI orchestrator to join the meeting via Nylas API.
    """
    try:
        tenant_id = user.tenant_id
        user_id = user.sub
        
        # Get call to find calendar event
        from app.services.db_helpers import get_call
        call = await get_call(session, call_id, tenant_id)
        
        if not call:
            raise HTTPException(status_code=404, detail="Call not found")
        
        if not call.calendar_event_id:
            raise HTTPException(
                status_code=400,
                detail="Call is not associated with a calendar event"
            )
        
        # Use orchestrator to join (runs in thread pool)
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            auto_join_meeting,
            call.calendar_event_id,
            tenant_id,
            user_id,
            None  # Let orchestrator create its own session
        )
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error joining meeting: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/meetings/upcoming", tags=["auto-join"])
async def get_upcoming_meetings(
    hours_ahead: int = 24,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get upcoming meetings that can be auto-joined.
    """
    try:
        tenant_id = user.tenant_id
        user_id = user.sub
        
        time_min = datetime.now(pytz.UTC)
        time_max = time_min + timedelta(hours=hours_ahead)
        
        events = await get_upcoming_calendar_events(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            time_min=time_min,
            time_max=time_max
        )
        
        meetings = []
        for event in events:
            meetings.append({
                "calendar_event_id": event.id,
                "title": event.title,
                "start_time": event.start_time.isoformat(),
                "meeting_link": event.meeting_link,
                "platform": event.meeting_platform,
                "status": event.status,
                "auto_join_enabled": True,  # Only returned if user has auto-join enabled
                "already_joined": event.status in ["joined", "completed"]
            })
        
        return {
            "meetings": meetings,
            "count": len(meetings)
        }
    
    except Exception as e:
        logger.error(f"Error getting upcoming meetings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/v1/meetings/auto-join/enable", tags=["auto-join"])
async def enable_auto_join(
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Enable auto-join for the authenticated user.
    """
    try:
        tenant_id = user.tenant_id
        user_id = user.sub
        
        from app.services.db_helpers import get_or_create_user_settings, update_user_settings
        
        settings = await get_or_create_user_settings(session, tenant_id, user_id)
        
        if not settings.google_calendar_enabled:
            raise HTTPException(
                status_code=400,
                detail="Google Calendar must be enabled before enabling auto-join"
            )
        
        await update_user_settings(
            session,
            tenant_id,
            user_id,
            auto_join_enabled=True
        )
        
        await session.commit()
        
        return {
            "success": True,
            "message": "Auto-join enabled successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enabling auto-join: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/v1/meetings/auto-join/disable", tags=["auto-join"])
async def disable_auto_join(
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Disable auto-join for the authenticated user.
    """
    try:
        tenant_id = user.tenant_id
        user_id = user.sub
        
        from app.services.db_helpers import update_user_settings
        
        await update_user_settings(
            session,
            tenant_id,
            user_id,
            auto_join_enabled=False
        )
        
        await session.commit()
        
        return {
            "success": True,
            "message": "Auto-join disabled successfully"
        }
    
    except Exception as e:
        logger.error(f"Error disabling auto-join: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
