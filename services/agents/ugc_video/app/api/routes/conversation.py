"""
Conversation endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import sys
from pathlib import Path
from app.core.dependencies import get_db_session
from app.core.auth import AuthenticatedUser, require_tenant
from app.models.schemas import ConversationResponse, ConversationListResponse
from app.services import db_helpers

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

router = APIRouter()


@router.get("/v1/conversations", response_model=ConversationListResponse, tags=["conversations"])
async def list_conversations(
    user: AuthenticatedUser = Depends(require_tenant()),
    limit: int = Query(20, ge=1, le=100, description="Number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_db_session)
):
    """List tenant's conversations with pagination"""
    try:
        tenant_id = user.tenant_id
        conversations = await db_helpers.get_tenant_conversations(
            session, tenant_id, limit, offset
        )
        
        conversation_responses = []
        for conv in conversations:
            conv_data = await db_helpers.get_conversation_with_data(
                session, conv.id, tenant_id
            )
            if conv_data:
                conversation_responses.append(ConversationResponse(**conv_data))
        
        return ConversationListResponse(
            conversations=conversation_responses,
            total=len(conversation_responses),
            limit=limit,
            offset=offset
        )
    except HTTPException:
        raise
    except Exception as e:
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )


@router.get("/v1/conversations/{conversation_id}", response_model=ConversationResponse, tags=["conversations"])
async def get_conversation(
    conversation_id: str,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Retrieve conversation history from database
    
    Requires authentication with tenant_id.
    """
    try:
        tenant_id = user.tenant_id
        
        # Verify ownership
        if not await db_helpers.verify_conversation_ownership(session, conversation_id, tenant_id):
            raise_standard_error(
                status_code=404,
                message="Conversation not found",
                detail="Conversation not found or access denied"
            )
        
        conversation_data = await db_helpers.get_conversation_with_data(
            session, conversation_id, tenant_id
        )
        
        if not conversation_data:
            raise_standard_error(
                status_code=404,
                message="Conversation not found",
                detail=f"Conversation with ID '{conversation_id}' not found for this tenant"
            )
        
        return ConversationResponse(**conversation_data)
    except HTTPException:
        raise
    except Exception as e:
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )


@router.delete("/v1/conversations/{conversation_id}", tags=["conversations"])
async def delete_conversation(
    conversation_id: str,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Delete conversation and all related data
    
    Requires authentication with tenant_id.
    """
    try:
        tenant_id = user.tenant_id
        
        # Verify ownership before deletion
        if not await db_helpers.verify_conversation_ownership(session, conversation_id, tenant_id):
            raise_standard_error(
                status_code=404,
                message="Conversation not found",
                detail="Conversation not found or access denied"
            )
        
        deleted = await db_helpers.delete_conversation(session, conversation_id, tenant_id)
        
        if not deleted:
            raise_standard_error(
                status_code=404,
                message="Conversation not found",
                detail=f"Conversation with ID '{conversation_id}' not found for this tenant"
            )
        
        return {"status": "deleted", "conversation_id": conversation_id}
    except HTTPException:
        raise
    except Exception as e:
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )


@router.get("/v1/conversations/{conversation_id}/assets", tags=["conversations"])
async def list_conversation_assets(
    conversation_id: str,
    asset_type: Optional[str] = None,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """
    List all assets (images, audio, video) for a conversation.
    
    Requires authentication with tenant_id.
    Optionally filter by asset_type (e.g., 'generated_image', 'audio', 'video').
    """
    try:
        tenant_id = user.tenant_id
        
        # Verify conversation ownership
        if not await db_helpers.verify_conversation_ownership(session, conversation_id, tenant_id):
            raise_standard_error(
                status_code=404,
                message="Conversation not found",
                detail="Conversation not found or access denied"
            )
        
        # Get assets for conversation
        assets = await db_helpers.get_assets(session, conversation_id, tenant_id, asset_type=asset_type)
        
        return {
            "assets": [
                {
                    "id": asset.id,
                    "conversation_id": asset.conversation_id,
                    "asset_type": asset.asset_type,
                    "url": asset.url,
                    "filename": asset.filename,
                    "metadata": asset.metadata,
                    "created_at": asset.created_at.isoformat() if asset.created_at else None
                }
                for asset in assets
            ],
            "total": len(assets),
            "conversation_id": conversation_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )
