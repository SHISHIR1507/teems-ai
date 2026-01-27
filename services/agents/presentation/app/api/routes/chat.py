"""
Chat router - AI chat interface powered by CrewAI
"""
from fastapi import APIRouter, HTTPException, Depends
import sys
from pathlib import Path

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
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db_session
from app.core.auth import AuthenticatedUser, require_tenant
from app.models.schemas import ChatRequest, ChatResponse
from app.orchestrator.presentation_orchestrator import (
    chat_with_presentation_specialist,
    generate_presentation_orchestrated
)
from app.services.db_helpers import (
    get_or_create_conversation,
    add_message,
    create_presentation,
    create_task
)
from app.services.realtime_notifier import notify_presentation_generation_started
import uuid

router = APIRouter()


@router.post("/v1/chat", response_model=ChatResponse, tags=["chat"])
async def chat(
    request: ChatRequest,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
) -> ChatResponse:
    """
    Chat with AI assistant powered by CrewAI to create and manage presentations.
    
    Requires authentication with tenant_id.
    
    The agent can:
    - Generate presentations from text or documents
    - Edit existing presentations
    - Upload and process documents
    - Manage templates and branding
    - Check task status and download presentations
    
    Send natural language messages like:
    - "Create a 10-slide presentation about quantum computing"
    - "Edit my last presentation to add a slide about market trends"
    - "What templates are available?"
    """
    try:
        tenant_id = user.tenant_id  # From authenticated user
        conversation_id = request.conversation_id or str(uuid.uuid4())
        
        # Get or create conversation
        conversation = await get_or_create_conversation(
            session, conversation_id, tenant_id, user.sub
        )
        
        # Add user message to database
        await add_message(session, conversation_id, tenant_id, "user", request.message)
        
        # Get brand context
        brand_context = None
        if conversation.brand_locked:
            brand_context = {
                "locked": True,
                "logo_url": conversation.brand_logo_url,
                "primary_color": conversation.brand_primary_color,
                "secondary_color": conversation.brand_secondary_color,
                "font": conversation.brand_font
            }
        
        # Determine if this is a generation request
        is_generation = any(keyword in request.message.lower() for keyword in [
            "create", "generate", "make", "build", "new presentation"
        ])
        
        if is_generation:
            # Use orchestrator for generation
            result = generate_presentation_orchestrated(
                user_message=request.message,
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                brand_context=brand_context
            )
            
            # Extract task_id from result
            task_id = result.get("task_id")
            if task_id:
                # Create presentation record
                presentation = await create_presentation(
                    session,
                    conversation_id,
                    tenant_id,
                    user.sub,
                    title=None,  # Will be updated later
                    slidespeak_task_id=task_id,
                    metadata={"user_message": request.message}
                )
                
                # Create task record
                await create_task(
                    session,
                    tenant_id,
                    "generate",
                    task_id,
                    user.sub,
                    conversation_id
                )
                
                # Notify frontend that generation has started
                await notify_presentation_generation_started(
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    task_id=task_id,
                    presentation_id=presentation.id,
                    estimated_time_seconds=60
                )
                
                assistant_message = result.get("message", "Presentation generation started!")
                
                # Build status URL for frontend to poll (relative path)
                status_url = f"/v1/tasks/{task_id}/status"
                
                return ChatResponse(
                    message=assistant_message,
                    action_taken="presentation_generation_started",
                    task_id=task_id,
                    presentation_id=presentation.id,
                    conversation_id=conversation_id,
                    status_url=status_url
                )
            else:
                # Generation failed or not started
                return ChatResponse(
                    message=result.get("message", "I couldn't start the presentation generation. Please try again."),
                    action_taken="error",
                    conversation_id=conversation_id
                )
        else:
            # General chat
            result = chat_with_presentation_specialist(request.message, brand_context)
            
            # Add assistant message to database
            await add_message(session, conversation_id, tenant_id, "assistant", result)
            
            return ChatResponse(
                message=result,
                action_taken="chat",
                conversation_id=conversation_id
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )
