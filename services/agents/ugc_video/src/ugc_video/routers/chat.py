"""
Chat and conversation management endpoints
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from ..auth import AuthenticatedUser, require_tenant
from ..dependencies import get_db_session
from ..models.conversation import Conversation, Message, MessageRole, ConversationStatus, UGCType
from ..models.artifact import Artifact, ArtifactType
from ..schemas.chat import ChatRequest, ChatResponse, GenerateVideoRequest, GenerateVideoResponse
from ..schemas.artifact import ArtifactResponse
from ..services.storage import S3StorageService
from ..dependencies import get_storage_service_dep
from ..services.type_detector import UGCTypeDetector
from ..services.orchestrator import UGCOrchestrator
from ..config import get_settings

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    message: str = Form(...),
    person_image: Optional[UploadFile] = File(None),
    product_image: Optional[UploadFile] = File(None),
    screenshot: Optional[UploadFile] = File(None),
    logo: Optional[UploadFile] = File(None),
    conversation_id: Optional[str] = Form(None),
    user: AuthenticatedUser = Depends(require_tenant()),
    db: AsyncSession = Depends(get_db_session),
    storage_service: S3StorageService = Depends(get_storage_service_dep),
):
    """
    Main chat endpoint - handles agent execution and image generation.
    Auto-detects UGC type based on uploaded files.
    """
    try:
        # Get or create conversation
        if conversation_id:
            conv_id = uuid.UUID(conversation_id)
            result = await db.execute(
                select(Conversation).where(
                    Conversation.id == conv_id,
                    Conversation.tenant_id == user.tenant_id
                )
            )
            conversation = result.scalar_one_or_none()
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
        else:
            conversation = Conversation(
                tenant_id=user.tenant_id,
                user_id=user.sub,
                status=ConversationStatus.ACTIVE
            )
            db.add(conversation)
            await db.flush()

        # Read uploaded files
        person_image_bytes = None
        product_image_bytes = None
        screenshot_bytes = None
        logo_bytes = None

        if person_image:
            person_image_bytes = await person_image.read()
        if product_image:
            product_image_bytes = await product_image.read()
        if screenshot:
            screenshot_bytes = await screenshot.read()
        if logo:
            logo_bytes = await logo.read()

        # Auto-detect UGC type
        ugc_type = UGCTypeDetector.detect_from_files(
            message=message,
            person_image=person_image_bytes,
            product_image=product_image_bytes,
            screenshot=screenshot_bytes,
            logo=logo_bytes
        )

        # Update conversation with detected type
        conversation.ugc_type = ugc_type
        await db.commit()
        await db.refresh(conversation)

        # Add user message
        user_message = Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=message,
            metadata={
                "has_person_image": person_image_bytes is not None,
                "has_product_image": product_image_bytes is not None,
                "has_screenshot": screenshot_bytes is not None,
                "has_logo": logo_bytes is not None
            }
        )
        db.add(user_message)
        await db.commit()

        # Create orchestrator
        orchestrator = UGCOrchestrator(
            db_session=db,
            storage_service=storage_service,
            conversation_id=conversation.id,
            tenant_id=user.tenant_id,
            user_id=user.sub
        )

        try:
            # Check if we should generate images
            if person_image_bytes and (product_image_bytes or screenshot_bytes or logo_bytes):
                # Generate images
                s3_keys = await orchestrator.generate_ugc_images(
                    person_image_bytes=person_image_bytes,
                    product_image_bytes=product_image_bytes,
                    screenshot_bytes=screenshot_bytes,
                    logo_bytes=logo_bytes,
                    base_intent=message,
                    ugc_type=ugc_type
                )

                # Get presigned URLs
                image_urls = [
                    storage_service.generate_presigned_url(key) for key in s3_keys
                ]

                assistant_message = f"Successfully generated {len(s3_keys)} UGC images! You can now select one to generate a video."
            else:
                # Just chat
                assistant_message = await orchestrator.chat_with_agent(message)
                image_urls = None

            # Add assistant message
            assistant_msg = Message(
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content=assistant_message,
                metadata={
                    "ugc_type": ugc_type.value,
                    "generated_images_count": len(image_urls) if image_urls else 0
                }
            )
            db.add(assistant_msg)
            await db.commit()

            return ChatResponse(
                conversation_id=conversation.id,
                assistant_message=assistant_message,
                ugc_type=ugc_type.value,
                generated_images=image_urls,
                status="completed",
                timestamp=assistant_msg.created_at
            )

        finally:
            orchestrator.cleanup()

    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")


@router.post("/chat/{conversation_id}/generate-video", response_model=GenerateVideoResponse)
async def generate_video(
    conversation_id: uuid.UUID,
    request: GenerateVideoRequest,
    user: AuthenticatedUser = Depends(require_tenant()),
    db: AsyncSession = Depends(get_db_session),
    storage_service: S3StorageService = Depends(get_storage_service_dep),
):
    """
    Generate video script and video from a selected image.
    """
    # Get conversation
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == user.tenant_id
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get image artifact
    result = await db.execute(
        select(Artifact).where(
            Artifact.id == request.image_id,
            Artifact.conversation_id == conversation_id,
            Artifact.artifact_type == ArtifactType.IMAGE
        )
    )
    image_artifact = result.scalar_one_or_none()
    if not image_artifact:
        raise HTTPException(status_code=404, detail="Image artifact not found")

    # Create orchestrator
    orchestrator = UGCOrchestrator(
        db_session=db,
        storage_service=storage_service,
        conversation_id=conversation_id,
        tenant_id=user.tenant_id,
        user_id=user.sub
    )

    try:
        # Generate video
        script, video_url = await orchestrator.generate_ugc_video(
            image_s3_key=image_artifact.s3_key,
            product_name=request.product_name,
            tone=request.tone,
            platform=request.platform,
            ugc_type=conversation.ugc_type or UGCType.PHYSICAL_PRODUCT
        )

        return GenerateVideoResponse(
            conversation_id=conversation_id,
            script=script,
            video_url=video_url,
            timestamp=conversation.updated_at
        )

    finally:
        orchestrator.cleanup()


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID,
    user: AuthenticatedUser = Depends(require_tenant()),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get conversation history with artifacts.
    """
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == user.tenant_id
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get messages
    result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()

    # Get artifacts
    result = await db.execute(
        select(Artifact).where(Artifact.conversation_id == conversation_id)
    )
    artifacts = result.scalars().all()

    return {
        "conversation_id": conversation.id,
        "ugc_type": conversation.ugc_type.value if conversation.ugc_type else None,
        "status": conversation.status.value,
        "messages": [
            {
                "id": str(msg.id),
                "role": msg.role.value,
                "content": msg.content,
                "created_at": msg.created_at.isoformat()
            }
            for msg in messages
        ],
        "artifacts": [ArtifactResponse.from_orm(art) for art in artifacts]
    }


@router.get("/conversations")
async def list_conversations(
    user: AuthenticatedUser = Depends(require_tenant()),
    db: AsyncSession = Depends(get_db_session),
    limit: int = 20,
    offset: int = 0,
):
    """
    List conversations for the authenticated user.
    """
    result = await db.execute(
        select(Conversation)
        .where(Conversation.tenant_id == user.tenant_id)
        .order_by(Conversation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    conversations = result.scalars().all()

    return {
        "conversations": [
            {
                "id": str(conv.id),
                "ugc_type": conv.ugc_type.value if conv.ugc_type else None,
                "status": conv.status.value,
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat()
            }
            for conv in conversations
        ],
        "total": len(conversations)
    }

