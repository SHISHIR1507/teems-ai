"""
Google Calendar integration endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging
import secrets

from app.core.dependencies import get_db_session
from app.core.auth import AuthenticatedUser, require_tenant
from app.services.google_calendar_service import google_calendar_service
from app.services.db_helpers import (
    get_or_create_user_settings,
    update_user_settings
)
from app.services.encryption_service import encryption_service
from app.orchestrator.meeting_orchestrator import sync_and_detect_meetings

logger = logging.getLogger(__name__)
router = APIRouter()

# Store OAuth state temporarily (in production, use Redis)
oauth_states = {}


@router.get("/v1/calendar/oauth/authorize", tags=["calendar"])
async def authorize_google_calendar(
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Initiate Google Calendar OAuth flow.
    
    Redirects user to Google OAuth consent screen.
    """
    try:
        tenant_id = user.tenant_id
        user_id = user.sub
        
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        oauth_states[state] = {
            "tenant_id": tenant_id,
            "user_id": user_id
        }
        
        # Get authorization URL
        auth_url = google_calendar_service.get_authorization_url(state=state)
        
        return RedirectResponse(url=auth_url)
    
    except Exception as e:
        logger.error(f"Error initiating OAuth: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/calendar/oauth/callback", tags=["calendar"])
async def oauth_callback(
    code: str,
    state: Optional[str] = None,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Handle Google OAuth callback.
    
    Exchanges authorization code for tokens and stores them encrypted.
    """
    try:
        # Verify state
        if not state or state not in oauth_states:
            raise HTTPException(status_code=400, detail="Invalid or missing state parameter")
        
        state_data = oauth_states.pop(state)
        tenant_id = state_data["tenant_id"]
        user_id = state_data["user_id"]
        
        # Exchange code for tokens
        tokens = google_calendar_service.exchange_code_for_tokens(code)
        
        # Create credentials object
        from google.oauth2.credentials import Credentials
        credentials = Credentials.from_authorized_user_info(tokens)
        
        # Encrypt credentials
        encrypted = google_calendar_service.encrypt_credentials(credentials)
        
        # Get or create user settings
        settings = await get_or_create_user_settings(session, tenant_id, user_id)
        
        # Update with OAuth tokens
        await update_user_settings(
            session,
            tenant_id,
            user_id,
            google_calendar_enabled=True,
            google_oauth_token=encrypted["encrypted_token"],
            google_oauth_refresh_token=encrypted["encrypted_refresh_token"]
        )
        
        await session.commit()
        
        return {
            "success": True,
            "message": "Google Calendar connected successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/v1/calendar/sync", tags=["calendar"])
async def sync_calendar(
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Manually trigger calendar sync.
    
    Uses CrewAI orchestrator to sync calendar and detect meetings.
    """
    try:
        tenant_id = user.tenant_id
        user_id = user.sub
        
        # Use orchestrator (runs in thread pool)
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            sync_and_detect_meetings,
            tenant_id,
            user_id,
            None  # Let orchestrator create its own session
        )
        
        return result
    
    except Exception as e:
        logger.error(f"Error syncing calendar: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/calendar/events", tags=["calendar"])
async def list_calendar_events(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """
    List calendar events for the authenticated user.
    """
    try:
        tenant_id = user.tenant_id
        user_id = user.sub
        
        from app.services.db_helpers import get_upcoming_calendar_events
        from datetime import datetime, timedelta
        import pytz
        
        time_min = datetime.now(pytz.UTC)
        time_max = time_min + timedelta(days=7)
        
        events = await get_upcoming_calendar_events(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            time_min=time_min,
            time_max=time_max
        )
        
        # Paginate
        total = len(events)
        events = events[offset:offset + limit]
        
        event_list = [
            {
                "id": event.id,
                "title": event.title,
                "start_time": event.start_time.isoformat(),
                "end_time": event.end_time.isoformat(),
                "meeting_link": event.meeting_link,
                "platform": event.meeting_platform,
                "status": event.status
            }
            for event in events
        ]
        
        return {
            "events": event_list,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    
    except Exception as e:
        logger.error(f"Error listing calendar events: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/calendar/settings", tags=["calendar"])
async def get_calendar_settings(
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get user's calendar settings.
    """
    try:
        tenant_id = user.tenant_id
        user_id = user.sub
        
        settings = await get_or_create_user_settings(session, tenant_id, user_id)
        
        return {
            "timezone": settings.timezone,
            "google_calendar_enabled": settings.google_calendar_enabled,
            "auto_join_enabled": settings.auto_join_enabled,
            "last_calendar_sync": settings.last_calendar_sync.isoformat() if settings.last_calendar_sync else None
        }
    
    except Exception as e:
        logger.error(f"Error getting calendar settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/v1/calendar/settings", tags=["calendar"])
async def update_calendar_settings(
    timezone: Optional[str] = None,
    auto_join_enabled: Optional[bool] = None,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Update user's calendar settings.
    """
    try:
        tenant_id = user.tenant_id
        user_id = user.sub
        
        updates = {}
        
        if timezone is not None:
            from app.services.timezone_service import timezone_service
            if not timezone_service.validate_timezone(timezone):
                raise HTTPException(status_code=400, detail=f"Invalid timezone: {timezone}")
            updates["timezone"] = timezone
        
        if auto_join_enabled is not None:
            updates["auto_join_enabled"] = auto_join_enabled
        
        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")
        
        await update_user_settings(session, tenant_id, user_id, **updates)
        await session.commit()
        
        return {
            "success": True,
            "message": "Settings updated successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating calendar settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
