"""
Conversation management endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db_session
from app.core.auth import AuthenticatedUser, require_tenant
from app.services.db_helpers import (
    get_conversation_with_data,
    verify_conversation_ownership
)
from sqlalchemy import delete
from app.core.database import Conversation

router = APIRouter()


@router.get("/v1/conversations/{conversation_id}", tags=["conversations"])
async def get_conversation_endpoint(
    conversation_id: str,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """Get conversation with all messages and presentations (tenant verified)"""
    try:
        tenant_id = user.tenant_id
        conversation_data = await get_conversation_with_data(session, conversation_id, tenant_id)
        
        if not conversation_data:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return conversation_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/v1/conversations/{conversation_id}", tags=["conversations"])
async def delete_conversation(
    conversation_id: str,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """Delete conversation and all related data (tenant verified)"""
    try:
        tenant_id = user.tenant_id
        
        # Verify ownership
        if not await verify_conversation_ownership(session, conversation_id, tenant_id):
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Delete from database (cascade will handle related records)
        await session.execute(
            delete(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.tenant_id == tenant_id
            )
        )
        await session.commit()
        
        return {"status": "deleted", "conversation_id": conversation_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
