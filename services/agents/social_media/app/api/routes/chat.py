"""
Chat router — single flow-driven Concierge. All conversation via LLM, no manual anchors.
"""
import asyncio
import concurrent.futures
from datetime import datetime
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
    from pyshared.ids import resolve_conversation_id
except ImportError:
    # Fallback if shared libs not available
    def raise_standard_error(status_code, message, detail=None, field=None):
        raise HTTPException(status_code=status_code, detail=message)
    def resolve_conversation_id(v):
        import uuid as _u
        return v if (v and str(v).strip() and str(v).strip().lower() not in {"string", "optional-uuid", "uuid"}) else str(_u.uuid4())
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
    get_recent_post_by_conversation,
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
        conversation_id = resolve_conversation_id(request.conversation_id)

        conv = await get_or_create_conversation(session, conversation_id, tenant_id, user.sub)
        await add_message(session, conversation_id, tenant_id, "user", request.message)
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

        # Parse scheduled_at if provided
        scheduled_at = None
        if request.scheduled_at:
            try:
                scheduled_at = datetime.fromisoformat(request.scheduled_at.replace('Z', '+00:00'))
            except Exception:
                # Invalid datetime format - will be handled by agent
                pass

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
            scheduled_at,
        )

        await add_message(session, conversation_id, tenant_id, "assistant", reply)
        
        # Check if a post was created (for immediate or scheduled posts)
        recent_post = await get_recent_post_by_conversation(session, conversation_id, tenant_id)
        
        post_status = None
        platform_post_id = None
        post_url = None
        scheduled_at = None
        scheduled_post_id = None
        
        if recent_post:
            post_status = recent_post.status
            platform_post_id = recent_post.publish_id
            scheduled_at = recent_post.scheduled_at.isoformat() if recent_post.scheduled_at else None
            scheduled_post_id = recent_post.id if recent_post.status == "scheduled" else None
            
            # Build post URL based on platform
            if platform_post_id:
                if recent_post.platform == "tiktok":
                    post_url = f"https://www.tiktok.com/@user/video/{platform_post_id}"  # Note: actual username needed
                elif recent_post.platform == "facebook":
                    post_url = f"https://www.facebook.com/{platform_post_id}"  # Note: actual format may vary

        return ChatResponse(
            message=reply,
            action_taken="chat",
            conversation_id=conversation_id,
            post_status=post_status,
            platform_post_id=platform_post_id,
            post_url=post_url,
            scheduled_at=scheduled_at,
            scheduled_post_id=scheduled_post_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )
