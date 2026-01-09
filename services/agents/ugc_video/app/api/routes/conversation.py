"""
Conversation endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db_session
from app.services import db_helpers

router = APIRouter()


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_db_session)
):
    """Retrieve conversation history from database"""
    conversation_data = await db_helpers.get_conversation_with_data(session, conversation_id)
    
    if not conversation_data:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return conversation_data


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_db_session)
):
    """Delete conversation and all related data"""
    deleted = await db_helpers.delete_conversation(session, conversation_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"status": "deleted", "conversation_id": conversation_id}
