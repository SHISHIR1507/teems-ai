"""
Database helper functions with tenant isolation
"""
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import Conversation, Message, Asset
from typing import Optional, List, Dict
from datetime import datetime


async def get_conversation(
    session: AsyncSession, 
    conversation_id: str, 
    tenant_id: str
) -> Optional[Conversation]:
    """Get conversation by ID with tenant verification"""
    result = await session.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none()


async def create_conversation(
    session: AsyncSession,
    conversation_id: str,
    tenant_id: str,
    user_id: Optional[str] = None,
    brand_industry: Optional[str] = None,
    brand_audience: Optional[str] = None,
    brand_vibe: Optional[str] = None,
    brand_locked: bool = False
) -> Conversation:
    """Create a new conversation"""
    conversation = Conversation(
        id=conversation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        brand_industry=brand_industry,
        brand_audience=brand_audience,
        brand_vibe=brand_vibe,
        brand_locked=brand_locked
    )
    session.add(conversation)
    await session.flush()
    return conversation


async def get_or_create_conversation(
    session: AsyncSession,
    conversation_id: str,
    tenant_id: str,
    user_id: Optional[str] = None
) -> Conversation:
    """Get or create conversation"""
    conversation = await get_conversation(session, conversation_id, tenant_id)
    if not conversation:
        conversation = await create_conversation(
            session, conversation_id, tenant_id, user_id
        )
    return conversation


async def verify_conversation_ownership(
    session: AsyncSession, 
    conversation_id: str, 
    tenant_id: str
) -> bool:
    """Verify that conversation belongs to tenant"""
    conversation = await get_conversation(session, conversation_id, tenant_id)
    return conversation is not None


async def update_conversation_brand(
    session: AsyncSession,
    conversation_id: str,
    tenant_id: str,
    industry: str,
    audience: str,
    vibe: str
) -> Optional[Conversation]:
    """Update conversation brand context with tenant verification"""
    conversation = await get_conversation(session, conversation_id, tenant_id)
    if conversation:
        conversation.brand_industry = industry
        conversation.brand_audience = audience
        conversation.brand_vibe = vibe
        conversation.brand_locked = True
        conversation.updated_at = datetime.utcnow()
        await session.flush()
    return conversation


async def update_product_name(
    session: AsyncSession,
    conversation_id: str,
    tenant_id: str,
    product_name: str
) -> Optional[Conversation]:
    """Update conversation product name with tenant verification"""
    conversation = await get_conversation(session, conversation_id, tenant_id)
    if conversation:
        conversation.product_name = product_name
        conversation.updated_at = datetime.utcnow()
        await session.flush()
    return conversation


async def add_message(
    session: AsyncSession,
    conversation_id: str,
    tenant_id: str,
    role: str,
    content: str
) -> Message:
    """Add a message to conversation with tenant verification"""
    # Verify conversation ownership
    conversation = await get_conversation(session, conversation_id, tenant_id)
    if not conversation:
        raise ValueError(f"Conversation {conversation_id} not found or access denied")
    
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content
    )
    session.add(message)
    await session.flush()
    return message


async def get_messages(
    session: AsyncSession, 
    conversation_id: str, 
    tenant_id: str
) -> List[Message]:
    """Get all messages for a conversation with tenant verification"""
    # Verify conversation ownership first
    conversation = await get_conversation(session, conversation_id, tenant_id)
    if not conversation:
        return []
    
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.timestamp)
    )
    return result.scalars().all()


async def add_asset(
    session: AsyncSession,
    conversation_id: str,
    tenant_id: str,
    user_id: Optional[str],
    asset_type: str,
    url: str,
    filename: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> Asset:
    """Add an asset to conversation with tenant verification"""
    # Verify conversation ownership
    conversation = await get_conversation(session, conversation_id, tenant_id)
    if not conversation:
        raise ValueError(f"Conversation {conversation_id} not found or access denied")
    
    asset = Asset(
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        asset_type=asset_type,
        url=url,
        filename=filename,
        asset_metadata=metadata
    )
    session.add(asset)
    await session.flush()
    return asset


async def get_assets(
    session: AsyncSession,
    conversation_id: str,
    tenant_id: str,
    asset_type: Optional[str] = None
) -> List[Asset]:
    """Get assets for a conversation with tenant verification, optionally filtered by type"""
    # Verify conversation ownership first
    conversation = await get_conversation(session, conversation_id, tenant_id)
    if not conversation:
        return []
    
    query = select(Asset).where(
        Asset.conversation_id == conversation_id,
        Asset.tenant_id == tenant_id
    )
    if asset_type:
        query = query.where(Asset.asset_type == asset_type)
    query = query.order_by(Asset.created_at)
    
    result = await session.execute(query)
    return result.scalars().all()


async def get_tenant_assets(
    session: AsyncSession,
    tenant_id: str,
    limit: int = 100,
    offset: int = 0,
    asset_type: Optional[str] = None
) -> List[Asset]:
    """Get assets for a tenant with pagination"""
    query = select(Asset).where(Asset.tenant_id == tenant_id)
    if asset_type:
        query = query.where(Asset.asset_type == asset_type)
    query = query.order_by(Asset.created_at.desc()).limit(limit).offset(offset)
    
    result = await session.execute(query)
    return result.scalars().all()


async def verify_asset_ownership(
    session: AsyncSession,
    asset_id: int,
    tenant_id: str
) -> bool:
    """Verify that asset belongs to tenant"""
    result = await session.execute(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none() is not None


async def delete_conversation(
    session: AsyncSession, 
    conversation_id: str, 
    tenant_id: str
) -> bool:
    """Delete a conversation and all related data with tenant verification"""
    result = await session.execute(
        delete(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == tenant_id
        )
    )
    await session.flush()
    return result.rowcount > 0


async def get_tenant_conversations(
    session: AsyncSession,
    tenant_id: str,
    limit: int = 100,
    offset: int = 0
) -> List[Conversation]:
    """Get conversations for a tenant with pagination"""
    result = await session.execute(
        select(Conversation)
        .where(Conversation.tenant_id == tenant_id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


async def get_conversation_state(
    session: AsyncSession,
    conversation_id: str,
    tenant_id: str
) -> Optional[Dict]:
    """
    Get the current conversation state including all assets
    
    Returns a dict with:
    - brand_locked, brand_industry, brand_audience, brand_vibe
    - person_url, avatar_id, product_url
    - generated_images (list of URLs)
    - has_person, has_product, has_generated_images (booleans)
    - next_step (suggested next action)
    """
    conversation = await get_conversation(session, conversation_id, tenant_id)
    if not conversation:
        return None
    
    # Get all assets
    assets = await get_assets(session, conversation_id, tenant_id)
    
    # Build state
    state = {
        "brand_locked": conversation.brand_locked if hasattr(conversation, 'brand_locked') else False,
        "brand_industry": conversation.brand_industry,
        "brand_audience": conversation.brand_audience,
        "brand_vibe": conversation.brand_vibe,
        "product_name": conversation.product_name if hasattr(conversation, 'product_name') else None,
        "person_url": None,
        "avatar_id": None,
        "product_url": None,
        "generated_images": [],
        "has_person": False,
        "has_product": False,
        "has_product_name": False,
        "has_generated_images": False,
        "next_step": None
    }
    
    # Extract asset URLs
    for asset in assets:
        if asset.asset_type == "uploaded_person":
            state["person_url"] = asset.url
            state["has_person"] = True
        elif asset.asset_type == "uploaded_product":
            state["product_url"] = asset.url
            state["has_product"] = True
        elif asset.asset_type == "generated_image":
            state["generated_images"].append(asset.url)
        elif asset.asset_type == "avatar_used":
            # Track when avatar was used instead of custom upload
            state["avatar_id"] = asset.asset_metadata.get("avatar_id") if asset.asset_metadata else None
            state["person_url"] = asset.url
            state["has_person"] = True
    
    # Check if we have generated images
    if state["generated_images"]:
        state["has_generated_images"] = True
    
    # Check if we have product name
    if state["product_name"]:
        state["has_product_name"] = True
    
    # Check if we have product name
    if state["product_name"]:
        state["has_product_name"] = True
    
    # Determine next step
    if not state["brand_locked"]:
        state["next_step"] = "sync_brand"
    elif not state["has_person"] and state["avatar_id"] is None:
        state["next_step"] = "upload_images_or_select_avatar"
    elif not state["has_product"]:
        state["next_step"] = "upload_product_image"
    elif state["has_generated_images"]:
        state["next_step"] = "regenerate_or_video"  # Final state - can regenerate or create videos
    else:
        state["next_step"] = "generate_ugc_images"
    
    return state


async def get_conversation_with_data(
    session: AsyncSession, 
    conversation_id: str, 
    tenant_id: str
) -> Optional[Dict]:
    """Get conversation with all messages and assets with tenant verification"""
    conversation = await get_conversation(session, conversation_id, tenant_id)
    if not conversation:
        return None
    
    messages = await get_messages(session, conversation_id, tenant_id)
    assets = await get_assets(session, conversation_id, tenant_id)
    
    return {
        "conversation_id": conversation.id,
        "tenant_id": conversation.tenant_id,
        "user_id": conversation.user_id,
        "brand": {
            "industry": conversation.brand_industry,
            "audience": conversation.brand_audience,
            "vibe": conversation.brand_vibe,
            "locked": conversation.brand_locked
        } if conversation.brand_locked else None,
        "messages": [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat()
            }
            for msg in messages
        ],
        "assets": [
            {
                "id": asset.id,
                "type": asset.asset_type,
                "url": asset.url,
                "filename": asset.filename,
                "metadata": asset.asset_metadata,
                "created_at": asset.created_at.isoformat()
            }
            for asset in assets
        ],
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat()
    }
