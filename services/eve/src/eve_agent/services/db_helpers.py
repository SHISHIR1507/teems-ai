"""
Database helper functions with tenant isolation
"""
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict, Any
from uuid import UUID
from ..models.document import Document, DocumentChunk
from ..models.conversation import Conversation, Message


async def get_document(
    session: AsyncSession, 
    document_id: UUID, 
    tenant_id: str
) -> Optional[Document]:
    """Get document by ID with tenant verification"""
    result = await session.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none()


async def list_documents(
    session: AsyncSession,
    tenant_id: str,
    limit: int = 100,
    offset: int = 0
) -> tuple[List[Document], int]:
    """List documents for a tenant with pagination. Returns (documents, total_count)"""
    # Get total count
    count_result = await session.execute(
        select(func.count(Document.id))
        .where(Document.tenant_id == tenant_id)
    )
    total = count_result.scalar() or 0
    
    # Get paginated documents
    result = await session.execute(
        select(Document)
        .where(Document.tenant_id == tenant_id)
        .order_by(Document.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return (list(result.scalars().all()), total)


async def create_document(
    session: AsyncSession,
    tenant_id: str,
    filename: str,
    s3_url: str,
    s3_key: str,
    file_size_bytes: int,
    status: str = "processing",
    metadata: Optional[dict] = None
) -> Document:
    """Create a new document record"""
    doc = Document(
        tenant_id=tenant_id,
        filename=filename,
        s3_url=s3_url,
        s3_key=s3_key,
        file_size_bytes=file_size_bytes,
        status=status,
        doc_metadata=metadata or {}
    )
    session.add(doc)
    await session.flush()
    return doc


async def update_document_status(
    session: AsyncSession,
    document_id: UUID,
    tenant_id: str,
    status: str,
    total_chunks: Optional[int] = None,
    metadata: Optional[dict] = None
) -> Optional[Document]:
    """Update document status and metadata"""
    doc = await get_document(session, document_id, tenant_id)
    if not doc:
        return None
    
    doc.status = status
    if total_chunks is not None:
        doc.total_chunks = total_chunks
    if metadata is not None:
        doc.doc_metadata = metadata
    
    await session.flush()
    return doc


async def delete_document(
    session: AsyncSession,
    document_id: UUID,
    tenant_id: str
) -> bool:
    """Delete document with tenant verification"""
    doc = await get_document(session, document_id, tenant_id)
    if not doc:
        return False
    
    await session.delete(doc)
    await session.flush()
    return True


async def verify_document_ownership(
    session: AsyncSession, 
    document_id: UUID, 
    tenant_id: str
) -> bool:
    """Verify that document belongs to tenant"""
    doc = await get_document(session, document_id, tenant_id)
    return doc is not None


async def get_document_chunks(
    session: AsyncSession,
    document_id: UUID,
    tenant_id: str
) -> List[DocumentChunk]:
    """Get all chunks for a document with tenant verification"""
    result = await session.execute(
        select(DocumentChunk).where(
            DocumentChunk.document_id == document_id,
            DocumentChunk.tenant_id == tenant_id
        ).order_by(DocumentChunk.chunk_index)
    )
    return list(result.scalars().all())


async def delete_document_chunks(
    session: AsyncSession,
    document_id: UUID
) -> int:
    """Delete all chunks for a document"""
    result = await session.execute(
        delete(DocumentChunk).where(
            DocumentChunk.document_id == document_id
        )
    )
    await session.flush()
    return result.rowcount


# Conversation helper functions

async def get_or_create_conversation(
    session: AsyncSession,
    tenant_id: str,
    session_id: str,
    user_id: Optional[str] = None
) -> Conversation:
    """Get existing conversation or create a new one for tenant+session"""
    # Try to get existing conversation
    result = await session.execute(
        select(Conversation).where(
            Conversation.tenant_id == tenant_id,
            Conversation.session_id == session_id
        )
    )
    conversation = result.scalar_one_or_none()
    
    if conversation:
        return conversation
    
    # Create new conversation
    conversation = Conversation(
        tenant_id=tenant_id,
        session_id=session_id,
        user_id=user_id
    )
    session.add(conversation)
    await session.flush()
    return conversation


async def get_conversation_by_session(
    session: AsyncSession,
    tenant_id: str,
    session_id: str
) -> Optional[Conversation]:
    """Get conversation by tenant_id and session_id"""
    result = await session.execute(
        select(Conversation).where(
            Conversation.tenant_id == tenant_id,
            Conversation.session_id == session_id
        )
    )
    return result.scalar_one_or_none()


async def create_message(
    session: AsyncSession,
    conversation_id: UUID,
    tenant_id: str,
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    sequence_number: Optional[int] = None
) -> Message:
    """Create a new message in a conversation"""
    # If sequence_number not provided, get the next sequence number
    if sequence_number is None:
        result = await session.execute(
            select(func.max(Message.sequence_number)).where(
                Message.conversation_id == conversation_id
            )
        )
        max_seq = result.scalar()
        sequence_number = (max_seq or 0) + 1
    
    message = Message(
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        role=role,
        content=content,
        metadata=metadata,
        sequence_number=sequence_number
    )
    session.add(message)
    await session.flush()
    return message


async def get_conversation_messages(
    session: AsyncSession,
    conversation_id: UUID,
    tenant_id: str,
    limit: Optional[int] = None
) -> List[Message]:
    """Get messages for a conversation, ordered by sequence_number"""
    query = select(Message).where(
        Message.conversation_id == conversation_id,
        Message.tenant_id == tenant_id
    ).order_by(Message.sequence_number.desc())
    
    if limit:
        query = query.limit(limit)
    
    result = await session.execute(query)
    messages = list(result.scalars().all())
    # Reverse to get chronological order (oldest first)
    return list(reversed(messages))


async def delete_conversation(
    session: AsyncSession,
    conversation_id: UUID,
    tenant_id: str
) -> bool:
    """Delete conversation and all its messages (cascade)"""
    result = await session.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == tenant_id
        )
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        return False
    
    await session.delete(conversation)
    await session.flush()
    return True


async def list_conversations(
    session: AsyncSession,
    tenant_id: str,
    limit: int = 100,
    offset: int = 0
) -> List[Conversation]:
    """List conversations for a tenant with pagination"""
    result = await session.execute(
        select(Conversation)
        .where(Conversation.tenant_id == tenant_id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())
