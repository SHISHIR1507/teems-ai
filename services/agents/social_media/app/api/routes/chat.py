"""
Chat router — single flow-driven Concierge. All conversation via LLM, no manual anchors.
"""
import uuid
import asyncio
import concurrent.futures
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.core.auth import AuthenticatedUser, require_tenant
from app.models.schemas import ChatRequest, ChatResponse
from app.orchestrator.social_media_orchestrator import run_chat_turn
from app.services.db_helpers import (
    get_or_create_conversation,
    add_message,
    get_conversation_messages,
    get_suggested_hashtags_list,
    get_pending_platforms_list,
)

router = APIRouter()
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)


@router.post("/v1/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session),
) -> ChatResponse:
    """Single conversational flow: content → suggest → feedback → confirm → post. No manual anchors."""
    try:
        tenant_id = user.tenant_id
        conversation_id = request.conversation_id or str(uuid.uuid4())

        conv = await get_or_create_conversation(session, conversation_id, tenant_id, user.sub)
        await add_message(session, conversation_id, "user", request.message)
        await session.flush()

        msgs = await get_conversation_messages(session, conversation_id, limit=20)
        recent = [
            {"role": m.role, "content": m.content}
            for m in reversed(msgs)
        ]

        stage = conv.stage or "collect_content"
        pending_asset_id = conv.pending_asset_id
        suggested_caption = conv.suggested_caption
        suggested_hashtags = get_suggested_hashtags_list(conv)
        pending_platforms = get_pending_platforms_list(conv)
        last_error = conv.last_error

        loop = asyncio.get_running_loop()
        reply = await loop.run_in_executor(
            _executor,
            run_chat_turn,
            conversation_id,
            tenant_id,
            user.sub,
            request.message,
            request.asset_id,
            recent,
            stage,
            pending_asset_id,
            suggested_caption,
            suggested_hashtags,
            pending_platforms,
            last_error,
        )

        await add_message(session, conversation_id, "assistant", reply)

        return ChatResponse(
            message=reply,
            action_taken="chat",
            conversation_id=conversation_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
