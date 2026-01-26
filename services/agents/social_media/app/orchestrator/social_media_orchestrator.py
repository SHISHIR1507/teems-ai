"""
Orchestrator for the posting flow. State machine, phase-specific prompts, no manual anchors.
All conversation through the Concierge LLM naturally.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Any, Dict, List, Optional

from crewai import Task, Crew

from app.agents.concierge_agent import create_concierge_agent
from app.tools.flow_tools import (
    register_content_link,
    get_conversation_assets,
    suggest_caption_hashtags,
)
from app.tools.platform_tools import get_connected_platforms, get_user_posts
from app.orchestrator.confirmation import user_confirmed_posting
from app.services.db_helpers import (
    run_with_db_session,
    get_asset,
    update_conversation_state,
)
from app.services.tiktok_service import TikTokService

executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

FLOW_TOOLS = [
    register_content_link,
    get_conversation_assets,
    suggest_caption_hashtags,
    get_connected_platforms,
    get_user_posts,
]


def _build_recent_context(messages: List[Dict[str, Any]], limit: int = 12) -> str:
    out = []
    for m in (messages or [])[-limit:]:
        role = (m.get("role") or "user").lower()
        content = (m.get("content") or "").strip()
        if not content:
            continue
        out.append(f"{role}: {content}")
    return "\n".join(out) if out else "(no prior messages)"


def _run_crew(agent: Any, task_desc: str, expected: str) -> str:
    task = Task(description=task_desc, expected_output=expected, agent=agent, human_input=False)
    crew = Crew(agents=[agent], tasks=[task], verbose=True, max_iter=6, full_output=False)
    try:
        future = executor.submit(crew.kickoff)
        return str(future.result(timeout=120))
    except concurrent.futures.TimeoutError:
        return "Sorry, that took too long. Please try again."
    except Exception as e:
        return f"Something went wrong: {str(e)}"


def _run_post_sync(tenant_id: str, user_id: str, video_url: str, caption: str, hashtags: List[str], conversation_id: Optional[str] = None) -> Dict[str, Any]:
    async def _post(session):
        svc = TikTokService(session, tenant_id)
        return await svc.post_video_async(
            user_id=user_id,
            video_url=video_url,
            caption=caption,
            hashtags=hashtags or [],
            conversation_id=conversation_id,
        )

    try:
        return asyncio.run(run_with_db_session(_post))
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _run_db(coro_fn):
    return asyncio.run(run_with_db_session(coro_fn))


def run_chat_turn(
    conversation_id: str,
    tenant_id: str,
    user_id: str,
    message: str,
    asset_id: Optional[str],
    recent_messages: List[Dict[str, Any]],
    stage: str,
    pending_asset_id: Optional[str],
    suggested_caption: Optional[str],
    suggested_hashtags: Optional[List[str]],
    pending_platforms: Optional[List[str]],
    last_error: Optional[str],
) -> str:
    """Run one chat turn. Updates state via DB. Returns assistant reply."""

    async def _link_asset(session):
        a = await get_asset(session, asset_id, tenant_id)
        if a:
            await update_conversation_state(
                session, conversation_id, tenant_id,
                stage="prepare_and_confirm",
                pending_asset_id=asset_id,
            )
        return a

    if asset_id:
        try:
            _run_db(_link_asset)
        except Exception:
            pass
        pending_asset_id = asset_id
        stage = "prepare_and_confirm"

    last_assistant = ""
    for m in reversed(recent_messages or []):
        if (m.get("role") or "").lower() == "assistant":
            last_assistant = (m.get("content") or "").strip()
            break

    context = _build_recent_context(recent_messages or [])

    if stage == "success":
        agent = create_concierge_agent(FLOW_TOOLS)
        task = (
            "The user's post was successfully published to TikTok. "
            "Respond warmly, confirm it's done, then ask how else you can help. Keep it brief and natural.\n\n"
            f"Recent context:\n{context}"
        )
        out = _run_crew(agent, task, "A short, friendly confirmation and offer to help further.")

        async def _reset_success(session):
            await update_conversation_state(session, conversation_id, tenant_id, stage="collect_content")

        try:
            _run_db(_reset_success)
        except Exception:
            pass
        return out

    if stage == "error":
        agent = create_concierge_agent(FLOW_TOOLS)
        task = (
            "Posting failed. Respond in a gentle, assistive way. Do not expose technical details. "
            "Say you're here to help when they're ready to try again. Keep it brief.\n\n"
            f"Recent context:\n{context}"
        )
        out = _run_crew(agent, task, "A brief, gentle message suggesting they try again.")

        async def _reset_error(session):
            await update_conversation_state(session, conversation_id, tenant_id, stage="collect_content")

        try:
            _run_db(_reset_error)
        except Exception:
            pass
        return out

    if stage == "prepare_and_confirm" and pending_asset_id and suggested_caption is not None:
        if user_confirmed_posting(message, last_assistant):
            async def _resolve(session):
                a = await get_asset(session, pending_asset_id, tenant_id)
                return a

            try:
                asset = _run_db(_resolve)
            except Exception:
                asset = None

            video_url = None
            if asset:
                video_url = asset.s3_url or asset.external_url
            if not video_url:
                async def _set_err(session):
                    await update_conversation_state(
                        session, conversation_id, tenant_id,
                        last_error="Content URL could not be resolved.",
                    )

                try:
                    _run_db(_set_err)
                except Exception:
                    pass
                return "I couldn't find the content to post. Please share it again (upload or link) and we'll try again."

            if getattr(asset, "asset_type", None) == "image":
                agent = create_concierge_agent(FLOW_TOOLS)
                task = (
                    "The user shared an image but TikTok requires a video. "
                    "Respond gently: we've saved the image, but they need to share a video to post to TikTok. "
                    "Offer to help once they have a video. Keep it brief. Stay in prepare_and_confirm.\n\n"
                    f"Recent context:\n{context}"
                )
                return _run_crew(agent, task, "A brief, gentle explanation.")

            platforms = pending_platforms or ["tiktok"]
            hashtags = suggested_hashtags or []
            caption = (suggested_caption or "")[:150]

            result = _run_post_sync(tenant_id, user_id, video_url, caption, hashtags, conversation_id)

            if result.get("status") == "success":
                async def _success(session):
                    await update_conversation_state(
                        session, conversation_id, tenant_id,
                        stage="success",
                        last_error=None,
                    )

                _run_db(_success)
                agent = create_concierge_agent(FLOW_TOOLS)
                task = (
                    "The user's post was successfully published to TikTok. "
                    "Respond warmly, confirm it's done, then ask how else you can help. Keep it brief and natural.\n\n"
                    f"Recent context:\n{context}"
                )
                return _run_crew(agent, task, "A short, friendly confirmation and offer to help further.")

            err = result.get("error") or "Posting failed."

            async def _fail(session):
                await update_conversation_state(
                    session, conversation_id, tenant_id,
                    stage="error",
                    last_error=err,
                )

            _run_db(_fail)
            agent = create_concierge_agent(FLOW_TOOLS)
            task = (
                "Posting failed. Respond in a gentle, assistive way. Do not expose technical details. "
                "Say you're here to help when they're ready to try again. Keep it brief.\n\n"
                f"Recent context:\n{context}"
            )
            return _run_crew(agent, task, "A brief, gentle message suggesting they try again.")

    phase = "collect_content" if stage == "collect_content" else "prepare_and_confirm"
    if phase == "collect_content":
        inst = (
            "We need content to post. Ask the user to upload an image or video (they can use the upload feature), "
            "or to share a direct link to their content. Use get_conversation_assets to check if we already have content. "
            "Once we have content, move on to suggesting a caption and hashtags. Be natural and friendly."
        )
    else:
        inst = (
            "We have content. Use suggest_caption_hashtags to propose a caption and hashtags, then present them to the user. "
            "Ask for feedback and revise if needed. When they're happy, use get_connected_platforms, then clearly ask "
            "if they want you to post to their TikTok account. Wait for their confirmation; do not post yourself. "
            "If they don't confirm, continue the conversation naturally and ask again when appropriate. Be natural and friendly."
        )

    agent = create_concierge_agent(FLOW_TOOLS)
    task_desc = (
        f"You are in phase: {phase}. Instructions: {inst}\n\n"
        f"User ID: {user_id}\nTenant ID: {tenant_id}\nConversation ID: {conversation_id}\n\n"
        f"Recent messages:\n{context}\n\n"
        f"User's latest message: {message}\n\n"
        "Respond naturally. Use tools when needed. Do not hallucinate."
    )
    return _run_crew(agent, task_desc, "A natural, helpful reply.")
