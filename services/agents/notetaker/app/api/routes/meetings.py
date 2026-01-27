"""
Meeting scheduling and chat endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Query
import sys
from pathlib import Path

# Add shared_libs to path for error standardization
current_file = Path(__file__).resolve()
shared_libs_dir = current_file.parent.parent.parent.parent.parent.parent / "platform" / "shared_libs"
if str(shared_libs_dir) not in sys.path:
    sys.path.insert(0, str(shared_libs_dir))

try:
    from pyshared.errors import raise_standard_error
except ImportError:
    # Fallback if shared libs not available
    def raise_standard_error(status_code, message, detail=None, field=None):
        raise HTTPException(status_code=status_code, detail=message)
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from typing import Optional
import logging

from app.core.dependencies import get_db_session
from app.core.auth import AuthenticatedUser, require_tenant
from app.schemas.request import ScheduleMeetingRequest, ChatRequest
from app.schemas.response import ScheduleMeetingResponse, ChatResponse, CallResponse
from app.services.db_helpers import (
    create_call,
    get_call,
    get_calls_by_tenant,
    update_call
)
from app.services.nylas_service import nylas_service
from app.services.rag_service import rag_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/v1/meetings/schedule", response_model=ScheduleMeetingResponse, tags=["meetings"])
async def schedule_meeting(
    request: ScheduleMeetingRequest,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
) -> ScheduleMeetingResponse:
    """
    Schedule a meeting with Nylas for automatic transcription.
    
    Requires authentication with tenant_id.
    
    The meeting will be:
    - Saved to the database
    - Scheduled with Nylas for transcription
    - Processed automatically when media is ready (via webhook)
    """
    try:
        tenant_id = user.tenant_id
        user_id = user.sub
        
        # Validate meeting link format
        meeting_link = request.meeting_link.strip()
        valid_domains = [
            "zoom.us", "zoom.com",
            "teams.microsoft.com", "teams.live.com",
            "meet.google.com",
            "webex.com", "cisco.com",
            "gotomeeting.com",
            "bluejeans.com"
        ]
        
        is_valid_link = False
        if meeting_link.startswith("http://") or meeting_link.startswith("https://"):
            from urllib.parse import urlparse
            parsed = urlparse(meeting_link)
            domain = parsed.netloc.lower()
            # Check if domain matches any valid meeting platform
            is_valid_link = any(valid_domain in domain for valid_domain in valid_domains)
        
        if not is_valid_link:
            raise_standard_error(
                status_code=400,
                message="Invalid meeting link format",
                detail="Please provide a valid meeting URL from supported platforms (Zoom, Teams, Google Meet, Webex, etc.). Example: https://zoom.us/j/123456789",
                field="meeting_link"
            )
        
        # Validate start_time format
        try:
            start_dt = datetime.fromisoformat(request.start_time.replace("Z", "+00:00"))
        except ValueError:
            raise_standard_error(
                status_code=400,
                message="Invalid start_time format",
                detail="Use ISO format (e.g., '2024-01-15T14:30:00Z')",
                field="start_time"
            )
        
        # Ensure start_time is in the future
        if start_dt <= datetime.now(timezone.utc):
            raise_standard_error(
                status_code=400,
                message="start_time must be in the future",
                field="start_time"
            )
        
        # Create call record in database first
        call = await create_call(
            session=session,
            tenant_id=tenant_id,
            user_id=user_id,
            title=request.title,
            meeting_link=request.meeting_link,
            start_time=start_dt
        )
        
        logger.info(f"Created call record: {call.id} - {request.title}")
        
        # Schedule with Nylas
        try:
            nylas_response = nylas_service.schedule_notetaker(
                meeting_link=request.meeting_link,
                start_time=request.start_time,
                name=request.title
            )
            
            # Extract Nylas meeting ID
            nylas_meeting_id = None
            if isinstance(nylas_response, dict):
                nylas_meeting_id = nylas_response.get("data", {}).get("id")
            
            # Update call with Nylas meeting ID
            if nylas_meeting_id:
                await update_call(
                    session=session,
                    call_id=call.id,
                    tenant_id=tenant_id,
                    meeting_id=nylas_meeting_id
                )
                logger.info(f"Linked call {call.id} to Nylas meeting {nylas_meeting_id}")
            
        except Exception as e:
            # If Nylas scheduling fails, delete the call record
            logger.error(f"Nylas scheduling failed for call {call.id}: {e}")
            await session.delete(call)
            await session.commit()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to schedule meeting with Nylas: {str(e)}"
            )
        
        # Build response
        call_response = CallResponse(
            id=call.id,
            tenant_id=call.tenant_id,
            user_id=call.user_id,
            meeting_id=call.meeting_id or nylas_meeting_id,
            title=call.title,
            meeting_link=call.meeting_link,
            start_time=call.start_time.isoformat(),
            transcript=call.transcript,
            summary=call.summary,
            action_items=call.action_items,
            status=call.status,
            created_at=call.created_at.isoformat(),
            updated_at=call.updated_at.isoformat(),
            has_transcript=bool(call.transcript),
            has_summary=bool(call.summary),
            has_action_items=bool(call.action_items)
        )
        
        return ScheduleMeetingResponse(
            success=True,
            message="Meeting scheduled and saved",
            call_id=call.id,
            call=call_response,
            nylas_meeting_id=nylas_meeting_id
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scheduling meeting: {e}", exc_info=True)
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )


@router.post("/v1/meetings/{call_id}/chat", response_model=ChatResponse, tags=["meetings"])
async def chat_about_meeting(
    call_id: str,
    request: ChatRequest,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
) -> ChatResponse:
    """
    Query a meeting using RAG-powered chat.
    
    Requires authentication with tenant_id.
    The call must belong to the user's tenant.
    
    Returns an AI-generated answer based on the meeting transcript.
    """
    try:
        tenant_id = user.tenant_id
        query = request.query.strip()
        
        if not query:
            raise HTTPException(status_code=400, detail="Query is required")
        
        # Get call with tenant verification
        call = await get_call(session, call_id, tenant_id)
        
        if not call:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        if not call.transcript:
            raise HTTPException(
                status_code=400,
                detail="No transcript available. The meeting may still be processing."
            )
        
        # Search relevant chunks
        relevant_chunks = await rag_service.search_relevant_chunks(
            query=query,
            call_id=call_id,
            db=session,
            top_k=5
        )
        
        if not relevant_chunks:
            return ChatResponse(
                answer="I couldn't find relevant information in the meeting notes for your question.",
                meeting_title=call.title,
                chunks_used=0,
                query=query
            )
        
        # Generate answer
        answer = await rag_service.generate_answer(
            query=query,
            context_chunks=relevant_chunks,
            meeting_title=call.title
        )
        
        return ChatResponse(
            answer=answer,
            meeting_title=call.title,
            chunks_used=len(relevant_chunks),
            query=query
        )
    
    except HTTPException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )
