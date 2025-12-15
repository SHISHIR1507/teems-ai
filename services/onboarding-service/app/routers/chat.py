from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
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


@router.post("", response_model=ChatResponse, summary="Chat endpoint for onboarding flow")
async def chat(
    payload: ChatRequest,
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
    conversation_id = payload.conversation_id or str(uuid4())
    
    stmt = select(OnboardingState).where(
        OnboardingState.conversation_id == conversation_id,
        OnboardingState.tenant_id == user.tenant_id,
    )
    result = await session.execute(stmt)
    state = result.scalar_one_or_none()

    if not state:
        # Create new onboarding state
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
            state, payload.message
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
            state, payload.message
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

