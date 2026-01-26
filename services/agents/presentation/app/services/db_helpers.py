"""
Database helper functions with tenant isolation
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from app.core.database import Conversation, Message, Presentation, Document, Task
from typing import Optional, List, Dict, Any
import uuid


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


async def add_message(session: AsyncSession, conversation_id: str, role: str, content: str) -> Message:
    """Add a message to conversation"""
    message = Message(conversation_id=conversation_id, role=role, content=content)
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


async def create_presentation(
    session: AsyncSession,
    conversation_id: str,
    tenant_id: str,
    user_id: Optional[str] = None,
    title: Optional[str] = None,
    slidespeak_task_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Presentation:
    """Create a new presentation record"""
    presentation = Presentation(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        title=title,
        slidespeak_task_id=slidespeak_task_id,
        metadata=metadata or {},
        status="pending"
    )
    session.add(presentation)
    await session.flush()
    return presentation


async def get_presentation(session: AsyncSession, presentation_id: str, tenant_id: str) -> Optional[Presentation]:
    """Get presentation by ID with tenant verification"""
    result = await session.execute(
        select(Presentation).where(
            Presentation.id == presentation_id,
            Presentation.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none()


async def verify_presentation_ownership(session: AsyncSession, presentation_id: str, tenant_id: str) -> bool:
    """Verify that presentation belongs to tenant"""
    presentation = await get_presentation(session, presentation_id, tenant_id)
    return presentation is not None


async def update_presentation(
    session: AsyncSession,
    presentation_id: str,
    tenant_id: str,
    **kwargs
) -> Optional[Presentation]:
    """Update presentation with tenant verification"""
    await session.execute(
        update(Presentation)
        .where(
            Presentation.id == presentation_id,
            Presentation.tenant_id == tenant_id
        )
        .values(**kwargs)
    )
    await session.flush()
    return await get_presentation(session, presentation_id, tenant_id)


async def get_tenant_presentations(
    session: AsyncSession,
    tenant_id: str,
    limit: int = 20,
    offset: int = 0
) -> List[Presentation]:
    """Get tenant's presentations"""
    result = await session.execute(
        select(Presentation)
        .where(Presentation.tenant_id == tenant_id)
        .order_by(Presentation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def create_document(
    session: AsyncSession,
    conversation_id: str,
    tenant_id: str,
    user_id: Optional[str] = None,
    filename: str = "",
    s3_url: str = "",
    s3_key: str = "",
    file_size: Optional[int] = None,
    content_type: Optional[str] = None
) -> Document:
    """Create a new document record"""
    document = Document(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        filename=filename,
        s3_url=s3_url,
        s3_key=s3_key,
        file_size=file_size,
        content_type=content_type,
        processing_status="uploaded"
    )
    session.add(document)
    await session.flush()
    return document


async def get_document(session: AsyncSession, document_id: str, tenant_id: str) -> Optional[Document]:
    """Get document by ID with tenant verification"""
    result = await session.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none()


async def update_document(
    session: AsyncSession,
    document_id: str,
    tenant_id: str,
    **kwargs
) -> Optional[Document]:
    """Update document with tenant verification"""
    await session.execute(
        update(Document)
        .where(
            Document.id == document_id,
            Document.tenant_id == tenant_id
        )
        .values(**kwargs)
    )
    await session.flush()
    return await get_document(session, document_id, tenant_id)


async def create_task(
    session: AsyncSession,
    tenant_id: str,
    task_type: str,
    slidespeak_task_id: str,
    user_id: Optional[str] = None,
    conversation_id: Optional[str] = None
) -> Task:
    """Create a new task record"""
    task = Task(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=user_id,
        conversation_id=conversation_id,
        task_type=task_type,
        slidespeak_task_id=slidespeak_task_id,
        status="pending"
    )
    session.add(task)
    await session.flush()
    return task


async def get_task(session: AsyncSession, task_id: str, tenant_id: str) -> Optional[Task]:
    """Get task by ID with tenant verification"""
    result = await session.execute(
        select(Task).where(
            Task.id == task_id,
            Task.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none()


async def verify_task_ownership(session: AsyncSession, task_id: str, tenant_id: str) -> bool:
    """Verify that task belongs to tenant"""
    task = await get_task(session, task_id, tenant_id)
    return task is not None


async def get_task_by_slidespeak_id(session: AsyncSession, slidespeak_task_id: str) -> Optional[Task]:
    """Get task by SlideSpeak task ID (for webhooks, no tenant check)"""
    result = await session.execute(
        select(Task).where(Task.slidespeak_task_id == slidespeak_task_id)
    )
    return result.scalar_one_or_none()


async def update_task(
    session: AsyncSession,
    task_id: str,
    tenant_id: str,
    **kwargs
) -> Optional[Task]:
    """Update task with tenant verification"""
    await session.execute(
        update(Task)
        .where(
            Task.id == task_id,
            Task.tenant_id == tenant_id
        )
        .values(**kwargs)
    )
    await session.flush()
    return await get_task(session, task_id, tenant_id)


async def update_conversation_brand(
    session: AsyncSession,
    conversation_id: str,
    tenant_id: str,
    brand_logo_url: Optional[str] = None,
    brand_primary_color: Optional[str] = None,
    brand_secondary_color: Optional[str] = None,
    brand_font: Optional[str] = None,
    brand_locked: bool = True
) -> Optional[Conversation]:
    """Update conversation brand settings with tenant verification"""
    await session.execute(
        update(Conversation)
        .where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == tenant_id
        )
        .values(
            brand_logo_url=brand_logo_url,
            brand_primary_color=brand_primary_color,
            brand_secondary_color=brand_secondary_color,
            brand_font=brand_font,
            brand_locked=brand_locked
        )
    )
    await session.flush()
    return await get_conversation(session, conversation_id, tenant_id)


async def get_conversation_with_data(session: AsyncSession, conversation_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
    """Get conversation with all related data (tenant verified)"""
    conversation = await get_conversation(session, conversation_id, tenant_id)
    if not conversation:
        return None
    
    messages = await get_conversation_messages(session, conversation_id)
    
    return {
        "id": conversation.id,
        "tenant_id": conversation.tenant_id,
        "user_id": conversation.user_id,
        "brand_locked": conversation.brand_locked,
        "brand_logo_url": conversation.brand_logo_url,
        "brand_primary_color": conversation.brand_primary_color,
        "brand_secondary_color": conversation.brand_secondary_color,
        "brand_font": conversation.brand_font,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None
            }
            for msg in messages
        ],
        "presentations": [
            {
                "id": pres.id,
                "title": pres.title,
                "status": pres.status,
                "s3_url": pres.s3_url,
                "created_at": pres.created_at.isoformat() if pres.created_at else None
            }
            for pres in conversation.presentations
        ]
    }
