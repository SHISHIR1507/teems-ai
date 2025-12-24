from typing import Annotated
from uuid import uuid4, UUID as UUIDType

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import AuthenticatedUser, require_tenant
from ..config import Settings
from ..database import get_session
from ..dependencies import (
    get_publisher_dep,
    get_settings_dep,
    get_llm_service_dep,
    get_brandfetch_client_dep,
)
from ..events import EventPublisher
from ..models import OnboardingState
from ..schemas import ChatRequest, ChatResponse
from ..services.llm import LLMService
from ..services.clients import BrandfetchClient
from ..services.stage_handler import StageHandler

router = APIRouter(prefix="/chat", tags=["chat"])


def _is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID format."""
    try:
        UUIDType(value)
        return True
    except (ValueError, TypeError, AttributeError):
        return False


@router.post("", response_model=ChatResponse, summary="Chat endpoint for onboarding flow")
async def chat(
    payload: ChatRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    llm_service: Annotated[LLMService, Depends(get_llm_service_dep)],
    brandfetch_client: Annotated[BrandfetchClient, Depends(get_brandfetch_client_dep)],
    publisher: Annotated[EventPublisher, Depends(get_publisher_dep)],
    user: AuthenticatedUser = Depends(require_tenant()),
) -> ChatResponse:
    """
    Main chat endpoint for onboarding. Handles all stages of onboarding flow.
    Creates or retrieves onboarding state and routes to appropriate stage handler.
    """
    if not user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have a tenant assigned",
        )

    # Get or create onboarding state
    # First, try to find existing onboarding state for this user (by tenant_id and user_id)
    # This ensures users resume their onboarding progress even after logging out/in
    # Conversation can be new or old - doesn't matter, we use the user's existing state
    existing_state_stmt = select(OnboardingState).where(
        OnboardingState.tenant_id == user.tenant_id,
        OnboardingState.user_id == user.sub,
    ).order_by(OnboardingState.created_at.desc()).limit(1)
    existing_result = await session.execute(existing_state_stmt)
    existing_state = existing_result.scalar_one_or_none()
    
    # If user has existing onboarding state, use it
    if existing_state:
        # Use existing state's conversation_id (conversation can be new or old)
        conversation_id = existing_state.conversation_id
        state = existing_state
    else:
        # No existing state - create new one
        # Generate conversation_id (can be from payload or new)
        if payload.conversation_id and _is_valid_uuid(payload.conversation_id):
            conversation_id = payload.conversation_id
        else:
            conversation_id = str(uuid4())
        
        state = OnboardingState(
            tenant_id=user.tenant_id,
            user_id=user.sub,
            conversation_id=conversation_id,
            current_stage="brand_discovery",
            extra_data={},
        )
        session.add(state)
        await session.flush()

    # Save user message
    from ..models import ConversationMessage
    user_message = ConversationMessage(
        conversation_id=conversation_id,
        role="user",
        content=payload.message,
        stage=state.current_stage,
    )
    session.add(user_message)
    await session.flush()

    # Extract auth token from request for service-to-service calls
    auth_token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        auth_token = auth_header[7:]  # Remove "Bearer " prefix

    # Create stage handler
    handler = StageHandler(
        session=session,
        settings=settings,
        llm_service=llm_service,
        brandfetch_client=brandfetch_client,
        publisher=publisher,
        user=user,
    )

    # Route to appropriate stage handler
    response_message = ""
    stage_completed = False

    if state.current_stage == "brand_discovery":
        response_message, stage_completed = await handler.handle_brand_discovery(
            state, payload.message, auth_token=auth_token
        )
    elif state.current_stage == "suggested_teammates":
        response_message, stage_completed = await handler.handle_suggested_teammates(
            state, payload.message
        )
    elif state.current_stage == "connect_world":
        response_message, stage_completed = await handler.handle_connect_world(
            state, payload.message
        )
    elif state.current_stage == "personalization":
        response_message, stage_completed = await handler.handle_personalization(
            state, payload.message
        )
    elif state.current_stage == "completed":
        # Onboarding already completed
        response_message = "Your onboarding is already complete! If you need to change anything, please use the settings."
    else:
        # Unknown stage, reset to brand discovery
        state.current_stage = "brand_discovery"
        response_message, stage_completed = await handler.handle_brand_discovery(
            state, payload.message, auth_token=auth_token
        )

    # Commit changes
    await session.commit()

    return ChatResponse(
        message=response_message,
        conversation_id=conversation_id,
        current_stage=state.current_stage,
        stage_completed=stage_completed,
        metadata={
            "brand_domain": state.brand_domain,
            "selected_teammates_count": len(state.selected_teammates or []),
            "connected_integrations_count": len(state.connected_integrations or []),
        },
    )

