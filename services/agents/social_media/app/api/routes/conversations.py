"""
Conversations router - list, get, delete
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.core.auth import AuthenticatedUser, require_tenant
from app.services.db_helpers import (
    get_tenant_conversations,
    get_conversation,
    get_conversation_messages,
    verify_conversation_ownership,
)
from sqlalchemy import delete
from app.core.database import Conversation

router = APIRouter()


@router.get("/v1/conversations")
async def list_conversations(
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List tenant's conversations"""
    try:
        tenant_id = user.tenant_id
        convos = await get_tenant_conversations(session, tenant_id, limit=limit, offset=offset)
        return {
            "conversations": [
                {
                    "id": c.id,
                    "tenant_id": c.tenant_id,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                }
                for c in convos
            ],
            "total": len(convos),
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/conversations/{conversation_id}")
async def get_conversation_detail(
    conversation_id: str,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session),
):
    """Get conversation with messages"""
    try:
        tenant_id = user.tenant_id
        convo = await get_conversation(session, conversation_id, tenant_id)
        if not convo:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        messages = await get_conversation_messages(session, conversation_id, limit=50)
        return {
            "id": convo.id,
            "tenant_id": convo.tenant_id,
            "created_at": convo.created_at.isoformat() if convo.created_at else None,
            "updated_at": convo.updated_at.isoformat() if convo.updated_at else None,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat() if m.timestamp else None,
                }
                for m in reversed(messages)
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/v1/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session),
):
    """Delete conversation"""
    try:
        tenant_id = user.tenant_id
        if not await verify_conversation_ownership(session, conversation_id, tenant_id):
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        await session.execute(
            delete(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.tenant_id == tenant_id,
            )
        )
        return {"status": "deleted", "conversation_id": conversation_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
