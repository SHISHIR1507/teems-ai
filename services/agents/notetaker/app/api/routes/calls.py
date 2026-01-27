"""
Call management endpoints
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
from typing import Optional

from app.core.dependencies import get_db_session
from app.core.auth import AuthenticatedUser, require_tenant
from app.schemas.response import CallResponse, CallListResponse
from app.services.db_helpers import (
    get_call,
    get_calls_by_tenant,
    delete_call
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/v1/calls", response_model=CallListResponse, tags=["calls"])
async def list_calls(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(None, description="Filter by status"),
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
) -> CallListResponse:
    """
    List calls for the authenticated tenant.
    
    Requires authentication with tenant_id.
    Supports pagination and status filtering.
    """
    try:
        tenant_id = user.tenant_id
        
        calls, total = await get_calls_by_tenant(
            session=session,
            tenant_id=tenant_id,
            limit=limit,
            offset=offset,
            status=status
        )
        
        call_responses = [
            CallResponse(
                id=call.id,
                tenant_id=call.tenant_id,
                user_id=call.user_id,
                meeting_id=call.meeting_id,
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
            for call in calls
        ]
        
        return CallListResponse(
            calls=call_responses,
            total=total,
            limit=limit,
            offset=offset
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing calls: {e}", exc_info=True)
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )


@router.get("/v1/calls/{call_id}", response_model=CallResponse, tags=["calls"])
async def get_call_details(
    call_id: str,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
) -> CallResponse:
    """
    Get call details by ID.
    
    Requires authentication with tenant_id.
    The call must belong to the user's tenant.
    """
    try:
        tenant_id = user.tenant_id
        
        call = await get_call(session, call_id, tenant_id)
        
        if not call:
            raise_standard_error(
                status_code=404,
                message="Call not found",
                detail=f"Call with ID '{call_id}' not found for this tenant"
            )
        
        return CallResponse(
            id=call.id,
            tenant_id=call.tenant_id,
            user_id=call.user_id,
            meeting_id=call.meeting_id,
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
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting call details: {e}", exc_info=True)
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )


@router.delete("/v1/calls/{call_id}", tags=["calls"])
async def delete_call_endpoint(
    call_id: str,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Delete a call.
    
    Requires authentication with tenant_id.
    The call must belong to the user's tenant.
    """
    try:
        tenant_id = user.tenant_id
        
        deleted = await delete_call(session, call_id, tenant_id)
        
        if not deleted:
            raise_standard_error(
                status_code=404,
                message="Call not found",
                detail=f"Call with ID '{call_id}' not found for this tenant"
            )
        
        return {"success": True, "message": "Call deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting call: {e}", exc_info=True)
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )


@router.get("/v1/calls/{call_id}/transcript", tags=["calls"])
async def get_transcript(
    call_id: str,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get raw transcript for a call.
    
    Requires authentication with tenant_id.
    """
    try:
        tenant_id = user.tenant_id
        
        call = await get_call(session, call_id, tenant_id)
        
        if not call:
            raise_standard_error(
                status_code=404,
                message="Call not found",
                detail=f"Call with ID '{call_id}' not found for this tenant"
            )
        
        if not call.transcript:
            raise_standard_error(
                status_code=404,
                message="Transcript not available",
                detail="Transcript not available. The meeting may still be processing."
            )
        
        return {"transcript": call.transcript}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting transcript: {e}", exc_info=True)
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )


@router.get("/v1/calls/{call_id}/summary", tags=["calls"])
async def get_summary(
    call_id: str,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get summary for a call.
    
    Requires authentication with tenant_id.
    """
    try:
        tenant_id = user.tenant_id
        
        call = await get_call(session, call_id, tenant_id)
        
        if not call:
            raise_standard_error(
                status_code=404,
                message="Call not found",
                detail=f"Call with ID '{call_id}' not found for this tenant"
            )
        
        if not call.summary:
            raise_standard_error(
                status_code=404,
                message="Summary not available",
                detail="Summary not available. The meeting may still be processing."
            )
        
        return {"summary": call.summary}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting summary: {e}", exc_info=True)
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )


@router.get("/v1/calls/{call_id}/action-items", tags=["calls"])
async def get_action_items(
    call_id: str,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get action items for a call.
    
    Requires authentication with tenant_id.
    """
    try:
        tenant_id = user.tenant_id
        
        call = await get_call(session, call_id, tenant_id)
        
        if not call:
            raise_standard_error(
                status_code=404,
                message="Call not found",
                detail=f"Call with ID '{call_id}' not found for this tenant"
            )
        
        if not call.action_items:
            raise_standard_error(
                status_code=404,
                message="Action items not available",
                detail="Action items not available. The meeting may still be processing."
            )
        
        return {"action_items": call.action_items}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting action items: {e}", exc_info=True)
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )
