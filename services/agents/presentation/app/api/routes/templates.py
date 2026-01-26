"""
Template and brand management endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db_session
from app.core.auth import AuthenticatedUser, require_tenant, get_current_user
from app.models.schemas import BrandSyncRequest, BrandSyncResponse
from app.services.db_helpers import (
    get_conversation,
    verify_conversation_ownership,
    update_conversation_brand
)
from app.orchestrator.presentation_orchestrator import handle_brand_sync
from app.services.slidespeak_client import get_slidespeak_client
from datetime import datetime

router = APIRouter()


@router.get("/v1/templates", tags=["templates"])
async def get_templates(
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Get all available templates (requires auth, no tenant needed)"""
    try:
        client = get_slidespeak_client()
        result = client.get_templates()
        
        templates = result.get("templates") or result.get("data", {}).get("templates", [])
        
        return {
            "templates": templates,
            "count": len(templates)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/templates/branded", tags=["templates"])
async def get_branded_templates(
    user: AuthenticatedUser = Depends(require_tenant())
):
    """Get branded templates (requires tenant)"""
    try:
        client = get_slidespeak_client()
        result = client.get_branded_templates()
        
        templates = result.get("templates") or result.get("data", {}).get("templates", [])
        
        return {
            "templates": templates,
            "count": len(templates)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/v1/brand/sync", response_model=BrandSyncResponse, tags=["brand"])
async def sync_brand(
    request: BrandSyncRequest,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """Sync brand settings (logos, colors, fonts) - requires tenant"""
    try:
        tenant_id = user.tenant_id
        
        # Verify conversation ownership
        if not await verify_conversation_ownership(session, request.conversation_id, tenant_id):
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Update brand settings
        await update_conversation_brand(
            session,
            request.conversation_id,
            tenant_id,
            brand_logo_url=request.logo_url,
            brand_primary_color=request.primary_color,
            brand_secondary_color=request.secondary_color,
            brand_font=request.font,
            brand_locked=True
        )
        
        # Get brand reflection from agent
        brand_message = handle_brand_sync(
            logo_url=request.logo_url,
            primary_color=request.primary_color,
            secondary_color=request.secondary_color,
            font=request.font
        )
        
        return BrandSyncResponse(
            conversation_id=request.conversation_id,
            message=brand_message,
            brand_locked=True,
            timestamp=datetime.now().isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/brand", tags=["brand"])
async def get_brand(
    conversation_id: str,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """Get current brand settings - requires tenant"""
    try:
        tenant_id = user.tenant_id
        
        # Verify conversation ownership
        conversation = await get_conversation(session, conversation_id, tenant_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return {
            "conversation_id": conversation_id,
            "brand_locked": conversation.brand_locked,
            "logo_url": conversation.brand_logo_url,
            "primary_color": conversation.brand_primary_color,
            "secondary_color": conversation.brand_secondary_color,
            "font": conversation.brand_font
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/info/credits", tags=["info"])
async def get_credits(
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Get API credits information (requires auth, no tenant needed)"""
    try:
        client = get_slidespeak_client()
        result = client.get_me()
        
        return {
            "username": result.get("username") or result.get("data", {}).get("username"),
            "credits": result.get("credits") or result.get("data", {}).get("credits"),
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
