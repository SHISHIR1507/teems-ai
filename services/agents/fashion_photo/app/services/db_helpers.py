"""
Database helper functions with tenant isolation
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from app.core.database import FashionSession, Avatar, Apparel, GeneratedImage, Message, Task
from typing import Optional, List, Dict, Any
import uuid


async def get_session(session: AsyncSession, session_id: str, tenant_id: str) -> Optional[FashionSession]:
    """Get session by ID with tenant verification"""
    result = await session.execute(
        select(FashionSession).where(
            FashionSession.id == session_id,
            FashionSession.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none()


async def create_session(
    session: AsyncSession,
    session_id: str,
    tenant_id: str,
    user_id: Optional[str] = None,
    stage: str = "CONVERSATION",
    metadata: Optional[Dict[str, Any]] = None
) -> FashionSession:
    """Create a new fashion session"""
    fashion_session = FashionSession(
        id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
        stage=stage,
        metadata=metadata or {}
    )
    session.add(fashion_session)
    await session.flush()
    return fashion_session


async def get_or_create_session(
    session: AsyncSession,
    session_id: str,
    tenant_id: str,
    user_id: Optional[str] = None
) -> FashionSession:
    """Get or create session"""
    fashion_session = await get_session(session, session_id, tenant_id)
    if not fashion_session:
        fashion_session = await create_session(session, session_id, tenant_id, user_id)
    return fashion_session


async def update_session_stage(
    session: AsyncSession,
    session_id: str,
    tenant_id: str,
    new_stage: str
) -> bool:
    """Update session stage"""
    result = await session.execute(
        update(FashionSession)
        .where(
            FashionSession.id == session_id,
            FashionSession.tenant_id == tenant_id
        )
        .values(stage=new_stage)
    )
    await session.flush()
    return result.rowcount > 0


async def update_session_metadata(
    session: AsyncSession,
    session_id: str,
    tenant_id: str,
    updates: Dict[str, Any]
) -> bool:
    """Update session metadata (merge with existing)."""
    fs = await get_session(session, session_id, tenant_id)
    if not fs or not fs.metadata:
        meta = dict(updates)
    else:
        meta = dict(fs.metadata)
        meta.update(updates)
    result = await session.execute(
        update(FashionSession)
        .where(
            FashionSession.id == session_id,
            FashionSession.tenant_id == tenant_id
        )
        .values(metadata=meta)
    )
    await session.flush()
    return result.rowcount > 0


async def verify_session_ownership(session: AsyncSession, session_id: str, tenant_id: str) -> bool:
    """Verify that session belongs to tenant"""
    fashion_session = await get_session(session, session_id, tenant_id)
    return fashion_session is not None


async def add_message(
    session: AsyncSession,
    session_id: str,
    tenant_id: str,
    role: str,
    content: str,
) -> Message:
    """Add a message to session"""
    message = Message(
        session_id=session_id,
        tenant_id=tenant_id,
        role=role,
        content=content,
    )
    session.add(message)
    await session.flush()
    return message


async def get_session_messages(session: AsyncSession, session_id: str, limit: int = 50) -> List[Message]:
    """Get session messages"""
    result = await session.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.timestamp.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def create_avatar(
    session: AsyncSession,
    session_id: str,
    tenant_id: str,
    s3_url: str,
    s3_key: str,
    user_id: Optional[str] = None,
    avatar_type: str = "uploaded",
    preset_url: Optional[str] = None,
    avatar_analysis: Optional[str] = None
) -> Avatar:
    """Create a new avatar record"""
    avatar = Avatar(
        id=str(uuid.uuid4()),
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
        s3_url=s3_url,
        s3_key=s3_key,
        avatar_type=avatar_type,
        preset_url=preset_url,
        avatar_analysis=avatar_analysis
    )
    session.add(avatar)
    await session.flush()
    return avatar


async def get_session_avatars(session: AsyncSession, session_id: str, tenant_id: str) -> List[Avatar]:
    """Get all avatars for a session"""
    result = await session.execute(
        select(Avatar).where(
            Avatar.session_id == session_id,
            Avatar.tenant_id == tenant_id
        ).order_by(Avatar.created_at.desc())
    )
    return list(result.scalars().all())


async def create_apparel(
    session: AsyncSession,
    session_id: str,
    tenant_id: str,
    s3_url: str,
    s3_key: str,
    user_id: Optional[str] = None,
    filename: Optional[str] = None,
    file_size: Optional[int] = None,
    content_type: Optional[str] = None,
    vision_analysis: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Apparel:
    """Create a new apparel record"""
    apparel = Apparel(
        id=str(uuid.uuid4()),
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
        s3_url=s3_url,
        s3_key=s3_key,
        filename=filename,
        file_size=file_size,
        content_type=content_type,
        vision_analysis=vision_analysis,
        metadata=metadata or {}
    )
    session.add(apparel)
    await session.flush()
    return apparel


async def get_session_apparel(session: AsyncSession, session_id: str, tenant_id: str) -> List[Apparel]:
    """Get all apparel for a session"""
    result = await session.execute(
        select(Apparel).where(
            Apparel.session_id == session_id,
            Apparel.tenant_id == tenant_id
        ).order_by(Apparel.created_at.desc())
    )
    return list(result.scalars().all())


async def create_generated_image(
    session: AsyncSession,
    session_id: str,
    tenant_id: str,
    s3_url: str,
    s3_key: str,
    user_id: Optional[str] = None,
    angle: Optional[str] = None,
    scene: Optional[str] = None,
    prompt: Optional[str] = None,
    generation_metadata: Optional[Dict[str, Any]] = None,
    task_id: Optional[str] = None,
    batch_id: Optional[str] = None,
    generation_type: str = "initial",
    edit_instruction: Optional[str] = None
) -> GeneratedImage:
    """Create a new generated image record"""
    image = GeneratedImage(
        id=str(uuid.uuid4()),
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
        s3_url=s3_url,
        s3_key=s3_key,
        angle=angle,
        scene=scene,
        prompt=prompt,
        generation_metadata=generation_metadata or {},
        task_id=task_id,
        batch_id=batch_id,
        generation_type=generation_type,
        edit_instruction=edit_instruction
    )
    session.add(image)
    await session.flush()
    return image


async def get_session_generated_images(
    session: AsyncSession,
    session_id: str,
    tenant_id: str,
    limit: int = 100,
    offset: int = 0,
    batch_id: Optional[str] = None
) -> List[GeneratedImage]:
    """Get generated images for a session, optionally filtered by batch_id."""
    q = select(GeneratedImage).where(
        GeneratedImage.session_id == session_id,
        GeneratedImage.tenant_id == tenant_id
    )
    if batch_id:
        q = q.where(GeneratedImage.batch_id == batch_id)
    result = await session.execute(
        q.order_by(GeneratedImage.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


async def count_session_generated_images(session: AsyncSession, session_id: str, tenant_id: str) -> int:
    """Count generated images for a session"""
    result = await session.execute(
        select(func.count(GeneratedImage.id)).where(
            GeneratedImage.session_id == session_id,
            GeneratedImage.tenant_id == tenant_id
        )
    )
    return result.scalar() or 0


async def get_last_batch_id(
    session: AsyncSession,
    session_id: str,
    tenant_id: str
) -> Optional[str]:
    """Get last generation batch_id from session metadata or latest GeneratedImage."""
    fs = await get_session(session, session_id, tenant_id)
    if fs and fs.metadata and fs.metadata.get("last_generation_batch_id"):
        return fs.metadata["last_generation_batch_id"]
    r = await session.execute(
        select(GeneratedImage.batch_id)
        .where(
            GeneratedImage.session_id == session_id,
            GeneratedImage.tenant_id == tenant_id,
            GeneratedImage.batch_id.isnot(None)
        )
        .order_by(GeneratedImage.created_at.desc())
        .limit(1)
    )
    row = r.first()
    return row[0] if row else None


async def create_task(
    session: AsyncSession,
    tenant_id: str,
    task_type: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    status: str = "pending",
    metadata: Optional[Dict[str, Any]] = None
) -> Task:
    """Create a new task record"""
    task = Task(
        id=str(uuid.uuid4()),
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
        task_type=task_type,
        status=status,
        metadata=metadata or {}
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


async def update_task_status(
    session: AsyncSession,
    task_id: str,
    tenant_id: str,
    status: str,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None
) -> bool:
    """Update task status"""
    result_data = {"status": status}
    if result is not None:
        result_data["result"] = result
    if error is not None:
        result_data["error"] = error
    
    db_result = await session.execute(
        update(Task)
        .where(
            Task.id == task_id,
            Task.tenant_id == tenant_id
        )
        .values(**result_data)
    )
    await session.flush()
    return db_result.rowcount > 0


async def delete_session(session: AsyncSession, session_id: str, tenant_id: str) -> bool:
    """Delete a session (cascade will delete related records)"""
    result = await session.execute(
        delete(FashionSession).where(
            FashionSession.id == session_id,
            FashionSession.tenant_id == tenant_id
        )
    )
    await session.flush()
    return result.rowcount > 0


async def list_user_sessions(
    session: AsyncSession,
    tenant_id: str,
    user_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[FashionSession]:
    """List sessions for a user/tenant"""
    query = select(FashionSession).where(
        FashionSession.tenant_id == tenant_id
    )
    if user_id:
        query = query.where(FashionSession.user_id == user_id)
    
    result = await session.execute(
        query.order_by(FashionSession.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())
