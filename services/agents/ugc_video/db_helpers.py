"""
Database helper functions for CRUD operations
"""
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from database import Conversation, Message, Asset
from typing import Optional, List, Dict
from datetime import datetime


async def create_conversation(
    session: AsyncSession,
    conversation_id: str,
    brand_industry: Optional[str] = None,
    brand_audience: Optional[str] = None,
    brand_vibe: Optional[str] = None,
    brand_locked: bool = False
) -> Conversation:
    """Create a new conversation"""
    conversation = Conversation(
        id=conversation_id,
        brand_industry=brand_industry,
        brand_audience=brand_audience,
        brand_vibe=brand_vibe,
        brand_locked=brand_locked
    )
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def get_conversation(session: AsyncSession, conversation_id: str) -> Optional[Conversation]:
    """Get conversation by ID"""
    result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    return result.scalar_one_or_none()


async def update_conversation_brand(
    session: AsyncSession,
    conversation_id: str,
    industry: str,
    audience: str,
    vibe: str
) -> Optional[Conversation]:
    """Update conversation brand context"""
    conversation = await get_conversation(session, conversation_id)
    if conversation:
        conversation.brand_industry = industry
        conversation.brand_audience = audience
        conversation.brand_vibe = vibe
        conversation.brand_locked = True
        conversation.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(conversation)
    return conversation


async def add_message(
    session: AsyncSession,
    conversation_id: str,
    role: str,
    content: str
) -> Message:
    """Add a message to conversation"""
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content
    )
    session.add(message)
    await session.commit()
    await session.refresh(message)
    return message


async def get_messages(session: AsyncSession, conversation_id: str) -> List[Message]:
    """Get all messages for a conversation"""
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.timestamp)
    )
    return result.scalars().all()


async def add_asset(
    session: AsyncSession,
    conversation_id: str,
    asset_type: str,
    url: str,
    filename: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> Asset:
    """Add an asset to conversation"""
    asset = Asset(
        conversation_id=conversation_id,
        asset_type=asset_type,
        url=url,
        filename=filename,
        asset_metadata=metadata  # Use asset_metadata instead of metadata
    )
    session.add(asset)
    await session.commit()
    await session.refresh(asset)
    return asset


async def get_assets(
    session: AsyncSession,
    conversation_id: str,
    asset_type: Optional[str] = None
) -> List[Asset]:
    """Get assets for a conversation, optionally filtered by type"""
    query = select(Asset).where(Asset.conversation_id == conversation_id)
    if asset_type:
        query = query.where(Asset.asset_type == asset_type)
    query = query.order_by(Asset.created_at)
    
    result = await session.execute(query)
    return result.scalars().all()


async def delete_conversation(session: AsyncSession, conversation_id: str) -> bool:
    """Delete a conversation and all related data"""
    result = await session.execute(
        delete(Conversation).where(Conversation.id == conversation_id)
    )
    await session.commit()
    return result.rowcount > 0


async def get_conversation_with_data(session: AsyncSession, conversation_id: str) -> Optional[Dict]:
    """Get conversation with all messages and assets"""
    conversation = await get_conversation(session, conversation_id)
    if not conversation:
        return None
    
    messages = await get_messages(session, conversation_id)
    assets = await get_assets(session, conversation_id)
    
    return {
        "conversation_id": conversation.id,
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
                "type": asset.asset_type,
                "url": asset.url,
                "filename": asset.filename,
                "metadata": asset.asset_metadata,  # Use asset_metadata
                "created_at": asset.created_at.isoformat()
            }
            for asset in assets
        ],
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat()
    }
