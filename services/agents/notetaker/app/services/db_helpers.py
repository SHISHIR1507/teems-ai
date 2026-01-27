"""
Database helper functions with tenant isolation
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, desc, and_, and_
from app.core.database import Call, CallChunk, UserSettings, CalendarEvent
from typing import Optional, List, Dict, Any
import uuid
from datetime import datetime


async def get_call(session: AsyncSession, call_id: str, tenant_id: str) -> Optional[Call]:
    """Get call by ID with tenant verification"""
    result = await session.execute(
        select(Call).where(
            Call.id == call_id,
            Call.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none()


async def create_call(
    session: AsyncSession,
    tenant_id: str,
    user_id: Optional[str],
    title: str,
    meeting_link: str,
    start_time: datetime,
    meeting_id: Optional[str] = None
) -> Call:
    """Create a new call record"""
    call = Call(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=user_id,
        title=title,
        meeting_link=meeting_link,
        start_time=start_time,
        meeting_id=meeting_id,
        status="scheduled"
    )
    session.add(call)
    await session.flush()
    return call


async def get_calls_by_tenant(
    session: AsyncSession,
    tenant_id: str,
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None
) -> tuple[List[Call], int]:
    """Get calls for a tenant with pagination"""
    query = select(Call).where(Call.tenant_id == tenant_id)
    
    if status:
        query = query.where(Call.status == status)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar_one()
    
    # Get paginated results
    query = query.order_by(desc(Call.created_at)).limit(limit).offset(offset)
    result = await session.execute(query)
    calls = list(result.scalars().all())
    
    return calls, total


async def update_call(
    session: AsyncSession,
    call_id: str,
    tenant_id: str,
    **updates
) -> Optional[Call]:
    """Update call fields (with tenant verification)"""
    call = await get_call(session, call_id, tenant_id)
    if not call:
        return None
    
    for key, value in updates.items():
        if hasattr(call, key):
            setattr(call, key, value)
    
    call.updated_at = datetime.utcnow()
    await session.flush()
    return call


async def delete_call(session: AsyncSession, call_id: str, tenant_id: str) -> bool:
    """Delete a call (with tenant verification)"""
    call = await get_call(session, call_id, tenant_id)
    if not call:
        return False
    
    await session.delete(call)
    await session.flush()
    return True


async def get_call_by_nylas_id(
    session: AsyncSession,
    nylas_meeting_id: str,
    tenant_id: Optional[str] = None
) -> Optional[Call]:
    """Get call by Nylas meeting ID (optionally filtered by tenant)"""
    query = select(Call).where(Call.meeting_id == nylas_meeting_id)
    if tenant_id:
        query = query.where(Call.tenant_id == tenant_id)
    
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_call_by_title(
    session: AsyncSession,
    title: str,
    tenant_id: Optional[str] = None
) -> Optional[Call]:
    """Get call by title (optionally filtered by tenant) - for webhook matching"""
    query = select(Call).where(Call.title == title)
    if tenant_id:
        query = query.where(Call.tenant_id == tenant_id)
    
    query = query.order_by(desc(Call.created_at))
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def verify_call_ownership(session: AsyncSession, call_id: str, tenant_id: str) -> bool:
    """Verify that call belongs to tenant"""
    call = await get_call(session, call_id, tenant_id)
    return call is not None


async def create_call_chunk(
    session: AsyncSession,
    call_id: str,
    tenant_id: str,
    chunk_index: int,
    content: str,
    embedding: List[float],
    content_type: str = "transcript"
) -> CallChunk:
    """Create a new call chunk with embedding"""
    chunk = CallChunk(
        id=str(uuid.uuid4()),
        call_id=call_id,
        tenant_id=tenant_id,
        chunk_index=chunk_index,
        content_type=content_type,
        content=content,
        embedding=embedding
    )
    session.add(chunk)
    await session.flush()
    return chunk


async def get_call_chunks(
    session: AsyncSession,
    call_id: str,
    limit: Optional[int] = None
) -> List[CallChunk]:
    """Get all chunks for a call"""
    query = select(CallChunk).where(CallChunk.call_id == call_id).order_by(CallChunk.chunk_index)
    if limit:
        query = query.limit(limit)
    
    result = await session.execute(query)
    return list(result.scalars().all())


async def delete_call_chunks(session: AsyncSession, call_id: str) -> int:
    """Delete all chunks for a call (returns count deleted)"""
    result = await session.execute(
        delete(CallChunk).where(CallChunk.call_id == call_id)
    )
    await session.flush()
    return result.rowcount


# UserSettings helpers
async def get_user_settings(session: AsyncSession, tenant_id: str, user_id: str) -> Optional[UserSettings]:
    """Get user settings by tenant and user ID"""
    result = await session.execute(
        select(UserSettings).where(
            and_(UserSettings.tenant_id == tenant_id, UserSettings.user_id == user_id)
        )
    )
    return result.scalar_one_or_none()


async def create_user_settings(
    session: AsyncSession,
    tenant_id: str,
    user_id: str,
    timezone: str = "UTC"
) -> UserSettings:
    """Create user settings"""
    settings = UserSettings(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=user_id,
        timezone=timezone
    )
    session.add(settings)
    await session.flush()
    return settings


async def get_or_create_user_settings(
    session: AsyncSession,
    tenant_id: str,
    user_id: str,
    timezone: str = "UTC"
) -> UserSettings:
    """Get or create user settings"""
    settings = await get_user_settings(session, tenant_id, user_id)
    if not settings:
        settings = await create_user_settings(session, tenant_id, user_id, timezone)
    return settings


async def update_user_settings(
    session: AsyncSession,
    tenant_id: str,
    user_id: str,
    **updates
) -> Optional[UserSettings]:
    """Update user settings"""
    settings = await get_user_settings(session, tenant_id, user_id)
    if not settings:
        return None
    
    for key, value in updates.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    
    settings.updated_at = datetime.utcnow()
    await session.flush()
    return settings


# CalendarEvent helpers
async def get_calendar_event(
    session: AsyncSession,
    event_id: str,
    tenant_id: str
) -> Optional[CalendarEvent]:
    """Get calendar event by ID with tenant verification"""
    result = await session.execute(
        select(CalendarEvent).where(
            and_(CalendarEvent.id == event_id, CalendarEvent.tenant_id == tenant_id)
        )
    )
    return result.scalar_one_or_none()


async def get_calendar_event_by_google_id(
    session: AsyncSession,
    google_event_id: str,
    tenant_id: Optional[str] = None
) -> Optional[CalendarEvent]:
    """Get calendar event by Google event ID"""
    query = select(CalendarEvent).where(CalendarEvent.google_event_id == google_event_id)
    if tenant_id:
        query = query.where(CalendarEvent.tenant_id == tenant_id)
    
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def create_calendar_event(
    session: AsyncSession,
    tenant_id: str,
    user_id: str,
    google_event_id: str,
    title: str,
    start_time: datetime,
    end_time: datetime,
    description: Optional[str] = None,
    meeting_link: Optional[str] = None,
    meeting_platform: Optional[str] = None
) -> CalendarEvent:
    """Create a calendar event"""
    event = CalendarEvent(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=user_id,
        google_event_id=google_event_id,
        title=title,
        description=description,
        start_time=start_time,
        end_time=end_time,
        meeting_link=meeting_link,
        meeting_platform=meeting_platform,
        status="synced"
    )
    session.add(event)
    await session.flush()
    return event


async def update_calendar_event(
    session: AsyncSession,
    event_id: str,
    tenant_id: str,
    **updates
) -> Optional[CalendarEvent]:
    """Update calendar event (with tenant verification)"""
    event = await get_calendar_event(session, event_id, tenant_id)
    if not event:
        return None
    
    for key, value in updates.items():
        if hasattr(event, key):
            setattr(event, key, value)
    
    event.updated_at = datetime.utcnow()
    await session.flush()
    return event


async def get_upcoming_calendar_events(
    session: AsyncSession,
    tenant_id: str,
    user_id: Optional[str] = None,
    time_min: Optional[datetime] = None,
    time_max: Optional[datetime] = None,
    limit: int = 50
) -> List[CalendarEvent]:
    """Get upcoming calendar events for auto-join"""
    query = select(CalendarEvent).where(CalendarEvent.tenant_id == tenant_id)
    
    if user_id:
        query = query.where(CalendarEvent.user_id == user_id)
    
    if time_min:
        query = query.where(CalendarEvent.start_time >= time_min)
    
    if time_max:
        query = query.where(CalendarEvent.start_time <= time_max)
    
    # Only get events with meeting links and not yet joined
    query = query.where(
        and_(
            CalendarEvent.meeting_link.isnot(None),
            CalendarEvent.status.in_(["synced", "scheduled"])
        )
    )
    
    query = query.order_by(CalendarEvent.start_time).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


async def delete_calendar_event(
    session: AsyncSession,
    event_id: str,
    tenant_id: str
) -> bool:
    """Delete a calendar event (with tenant verification)"""
    event = await get_calendar_event(session, event_id, tenant_id)
    if not event:
        return False
    
    await session.delete(event)
    await session.flush()
    return True
