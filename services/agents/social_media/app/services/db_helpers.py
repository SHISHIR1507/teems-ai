"""
Database helper functions with tenant isolation
"""
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from app.core.database import Conversation, Message, Post, UserToken, ContentAsset
from app.core import database as db_module
from typing import Optional, List, Dict, Any, Callable, Awaitable, TypeVar
import uuid
import asyncio
import json

T = TypeVar("T")


async def run_with_db_session(coro_fn: Callable[[AsyncSession], Awaitable[T]]) -> T:
    """
    Run an async function with a database session. Use from sync context (e.g. CrewAI tools).
    Creates session, runs coro, commits on success, rollback on error, closes session.
    """
    db_module.init_engine()
    assert db_module.async_session_maker is not None
    async with db_module.async_session_maker() as session:
        try:
            result = await coro_fn(session)
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise


async def get_conversation(session: AsyncSession, conversation_id: str, tenant_id: str) -> Optional[Conversation]:
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
    user_id: Optional[str] = None
) -> Conversation:
    """Create a new conversation"""
    conversation = Conversation(id=conversation_id, tenant_id=tenant_id, user_id=user_id)
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
        conversation = await create_conversation(session, conversation_id, tenant_id, user_id)
    return conversation


async def verify_conversation_ownership(session: AsyncSession, conversation_id: str, tenant_id: str) -> bool:
    """Verify that conversation belongs to tenant"""
    conversation = await get_conversation(session, conversation_id, tenant_id)
    return conversation is not None


async def add_message(
    session: AsyncSession,
    conversation_id: str,
    tenant_id: str,
    role: str,
    content: str,
) -> Message:
    """Add a message to conversation"""
    message = Message(
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        role=role,
        content=content,
    )
    session.add(message)
    await session.flush()
    return message


async def get_conversation_messages(session: AsyncSession, conversation_id: str, limit: int = 50) -> List[Message]:
    """Get conversation messages"""
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.timestamp.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_tenant_conversations(
    session: AsyncSession,
    tenant_id: str,
    limit: int = 20,
    offset: int = 0
) -> List[Conversation]:
    """Get tenant's conversations"""
    result = await session.execute(
        select(Conversation)
        .where(Conversation.tenant_id == tenant_id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def create_post(
    session: AsyncSession,
    conversation_id: Optional[str],
    tenant_id: str,
    user_id: Optional[str],
    platform: str,
    video_url: str,
    caption: Optional[str] = None,
    hashtags: Optional[List[str]] = None,
    publish_id: Optional[str] = None,
    status: str = "posted",
    extra: Optional[Dict[str, Any]] = None,
    scheduled_at: Optional[datetime] = None
) -> Post:
    """Create a post record"""
    post = Post(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        platform=platform,
        video_url=video_url,
        caption=caption,
        hashtags=",".join(hashtags) if hashtags else None,
        publish_id=publish_id,
        status=status,
        extra=extra,
        scheduled_at=scheduled_at
    )
    session.add(post)
    await session.flush()
    return post


async def get_post(session: AsyncSession, post_id: str, tenant_id: str) -> Optional[Post]:
    """Get post by ID with tenant verification"""
    result = await session.execute(
        select(Post).where(
            Post.id == post_id,
            Post.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none()


async def get_tenant_posts(
    session: AsyncSession,
    tenant_id: str,
    platform: Optional[str] = None,
    limit: int = 20,
    offset: int = 0
) -> List[Post]:
    """Get tenant's posts with optional platform filter"""
    query = select(Post).where(Post.tenant_id == tenant_id)
    if platform:
        query = query.where(Post.platform == platform)
    query = query.order_by(Post.created_at.desc()).limit(limit).offset(offset)
    
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_recent_post_by_conversation(
    session: AsyncSession,
    conversation_id: str,
    tenant_id: str
) -> Optional[Post]:
    """Get the most recent post for a conversation"""
    result = await session.execute(
        select(Post)
        .where(
            Post.conversation_id == conversation_id,
            Post.tenant_id == tenant_id
        )
        .order_by(Post.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def verify_post_ownership(session: AsyncSession, post_id: str, tenant_id: str) -> bool:
    """Verify that post belongs to tenant"""
    post = await get_post(session, post_id, tenant_id)
    return post is not None


async def update_post(
    session: AsyncSession,
    post_id: str,
    tenant_id: str,
    status: Optional[str] = None,
    error: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None
) -> Optional[Post]:
    """Update post (tenant verified)"""
    post = await get_post(session, post_id, tenant_id)
    if not post:
        return None
    
    if status is not None:
        post.status = status
    if error is not None:
        post.error = error
    if extra is not None:
        post.extra = extra
    
    await session.flush()
    return post


async def get_tenant_token(
    session: AsyncSession,
    tenant_id: str,
    platform: str
) -> Optional[UserToken]:
    """Get tenant's token for a platform"""
    result = await session.execute(
        select(UserToken).where(
            UserToken.tenant_id == tenant_id,
            UserToken.platform == platform
        )
    )
    return result.scalar_one_or_none()


async def get_tenant_tokens(
    session: AsyncSession,
    tenant_id: str
) -> List[UserToken]:
    """Get all tokens for a tenant"""
    result = await session.execute(
        select(UserToken).where(UserToken.tenant_id == tenant_id)
    )
    return list(result.scalars().all())


async def create_or_update_token(
    session: AsyncSession,
    tenant_id: str,
    user_id: Optional[str],
    platform: str,
    access_token: str,
    refresh_token: Optional[str] = None,
    platform_user_id: Optional[str] = None,
    expires_at: Optional[datetime] = None
) -> UserToken:
    """Create or update token for tenant"""
    
    existing = await get_tenant_token(session, tenant_id, platform)
    if existing:
        existing.access_token = access_token
        if refresh_token:
            existing.refresh_token = refresh_token
        if platform_user_id:
            existing.platform_user_id = platform_user_id
        if expires_at:
            existing.expires_at = expires_at
        existing.user_id = user_id
        await session.flush()
        return existing
    else:
        token = UserToken(
            tenant_id=tenant_id,
            user_id=user_id,
            platform=platform,
            access_token=access_token,
            refresh_token=refresh_token,
            platform_user_id=platform_user_id,
            expires_at=expires_at
        )
        session.add(token)
        await session.flush()
        return token


async def delete_token(
    session: AsyncSession,
    tenant_id: str,
    platform: str
) -> bool:
    """Delete token for tenant"""
    token = await get_tenant_token(session, tenant_id, platform)
    if not token:
        return False
    
    await session.delete(token)
    await session.flush()
    return True


# ---------- ContentAsset ----------


async def create_asset(
    session: AsyncSession,
    conversation_id: str,
    tenant_id: str,
    user_id: Optional[str],
    asset_type: str,
    source: str,
    s3_key: Optional[str] = None,
    s3_url: Optional[str] = None,
    external_url: Optional[str] = None,
    file_name: Optional[str] = None,
    content_type: Optional[str] = None,
    vision_analysis: Optional[str] = None,
) -> ContentAsset:
    """Create a content asset."""
    a = ContentAsset(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        asset_type=asset_type,
        source=source,
        s3_key=s3_key,
        s3_url=s3_url,
        external_url=external_url,
        file_name=file_name,
        content_type=content_type,
        vision_analysis=vision_analysis,
    )
    session.add(a)
    await session.flush()
    return a


async def get_asset(session: AsyncSession, asset_id: str, tenant_id: str) -> Optional[ContentAsset]:
    """Get asset by ID with tenant check."""
    r = await session.execute(
        select(ContentAsset).where(
            ContentAsset.id == asset_id,
            ContentAsset.tenant_id == tenant_id,
        )
    )
    return r.scalar_one_or_none()


async def get_conversation_assets(
    session: AsyncSession,
    conversation_id: str,
    tenant_id: str,
) -> List[ContentAsset]:
    """List assets for a conversation (tenant-scoped)."""
    r = await session.execute(
        select(ContentAsset)
        .where(
            ContentAsset.conversation_id == conversation_id,
            ContentAsset.tenant_id == tenant_id,
        )
        .order_by(ContentAsset.created_at.desc())
    )
    return list(r.scalars().all())


async def update_conversation_state(
    session: AsyncSession,
    conversation_id: str,
    tenant_id: str,
    stage: Optional[str] = None,
    pending_asset_id: Optional[str] = None,
    suggested_caption: Optional[str] = None,
    suggested_hashtags: Optional[List[str]] = None,
    pending_platforms: Optional[List[str]] = None,
    last_error: Optional[str] = None,
) -> Optional[Conversation]:
    """Update flow state for a conversation."""
    conv = await get_conversation(session, conversation_id, tenant_id)
    if not conv:
        return None
    if stage is not None:
        conv.stage = stage
    if pending_asset_id is not None:
        conv.pending_asset_id = pending_asset_id
    if suggested_caption is not None:
        conv.suggested_caption = suggested_caption
    if suggested_hashtags is not None:
        conv.suggested_hashtags = json.dumps(suggested_hashtags)
    if pending_platforms is not None:
        conv.pending_platforms = json.dumps(pending_platforms)
    if last_error is not None:
        conv.last_error = last_error
    await session.flush()
    return conv


def get_suggested_hashtags_list(conv: Conversation) -> List[str]:
    """Parse suggested_hashtags JSON from conversation."""
    if not conv or not conv.suggested_hashtags:
        return []
    try:
        out = json.loads(conv.suggested_hashtags)
        return out if isinstance(out, list) else []
    except Exception:
        return []


def get_pending_platforms_list(conv: Conversation) -> List[str]:
    """Parse pending_platforms JSON from conversation."""
    if not conv or not conv.pending_platforms:
        return []
    try:
        out = json.loads(conv.pending_platforms)
        return out if isinstance(out, list) else []
    except Exception:
        return []


async def update_asset_vision_analysis(
    session: AsyncSession,
    asset_id: str,
    tenant_id: str,
    vision_analysis: str,
) -> Optional[ContentAsset]:
    """Update vision_analysis for an asset."""
    asset = await get_asset(session, asset_id, tenant_id)
    if not asset:
        return None
    asset.vision_analysis = vision_analysis
    await session.flush()
    return asset
