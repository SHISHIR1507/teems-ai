"""
Meeting scheduling and chat endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Query
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
        
        # Validate start_time format
        try:
            start_dt = datetime.fromisoformat(request.start_time.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid start_time format. Use ISO format (e.g., '2024-01-15T14:30:00Z')"
            )
        
        # Ensure start_time is in the future
        if start_dt <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=400,
                detail="start_time must be in the future"
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
            updated_at=call.updated_at.isoformat()
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
        raise HTTPException(status_code=500, detail=str(e))


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
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
