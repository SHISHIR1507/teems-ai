"""
Flow-specific tools: content, caption/hashtag suggestions. No posting — orchestrator posts.
"""
from crewai.tools import tool
from typing import List, Optional
import asyncio
import json
import re

from app.services.db_helpers import (
    run_with_db_session,
    create_asset,
    get_or_create_conversation,
    update_conversation_state,
    get_asset,
    update_asset_vision_analysis,
    get_conversation,
)
from app.services.db_helpers import get_conversation_assets as _list_assets_db
from app.core.config import get_settings
from app.tools.vision_tools import analyze_content


def _call_llm(prompt: str, system: str = "") -> str:
    """Sync LLM call via AIML (OpenAI-compatible)."""
    s = get_settings()
    import requests
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    url = f"{s.aiml_base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {s.aiml_api_key}", "Content-Type": "application/json"}
    body = {"model": s.llm_model, "messages": messages, "max_tokens": 1024}
    r = requests.post(url, json=body, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    choice = data.get("choices") or []
    if not choice:
        return ""
    return (choice[0].get("message") or {}).get("content") or ""


@tool
def register_content_link(
    tenant_id: str,
    conversation_id: str,
    url: str,
    content_type: str = "video",
) -> str:
    """
    Register a content link (image or video URL) shared by the user for this conversation.
    Use when the user provides a direct link to image or video content.
    
    Args:
        tenant_id: Tenant ID
        conversation_id: Conversation ID
        url: Public URL of the image or video
        content_type: 'image' or 'video'
    
    Returns:
        Confirmation message with asset id
    """
    if content_type not in ("image", "video"):
        content_type = "video"
    try:
        # Analyze content with vision API
        vision_analysis = None
        try:
            vision_analysis = analyze_content(url, asset_type=content_type)
        except Exception:
            pass

        async def _create(session):
            await get_or_create_conversation(session, conversation_id, tenant_id, None)
            asset = await create_asset(
                session=session,
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                user_id=None,
                asset_type=content_type,
                source="link",
                external_url=url,
                vision_analysis=vision_analysis,
            )
            await update_conversation_state(
                session, conversation_id, tenant_id,
                stage="prepare_and_confirm",
                pending_asset_id=asset.id,
            )
            return asset.id

        aid = asyncio.run(run_with_db_session(_create))
        return f"Registered content link as {content_type}. Asset ID: {aid}. You can now suggest a caption and hashtags."
    except Exception as e:
        return f"Failed to register link: {str(e)}"


@tool
def get_conversation_assets(tenant_id: str, conversation_id: str) -> str:
    """
    List content assets (uploaded or linked) for this conversation.
    Use to check what content the user has provided before suggesting caption/hashtags.
    
    Args:
        tenant_id: Tenant ID
        conversation_id: Conversation ID
    
    Returns:
        Human-readable summary of assets
    """
    try:
        async def _list(session):
            assets = await _list_assets_db(session, conversation_id, tenant_id)
            return [{"id": a.id, "type": a.asset_type, "url": a.s3_url or a.external_url, "source": a.source} for a in assets]

        out = asyncio.run(run_with_db_session(_list))
        if not out:
            return "No content yet for this conversation. Ask the user to upload a file or share a link."
        lines = []
        for a in out:
            u = a.get("url") or "(no url)"
            lines.append(f"- {a.get('type', '?')} ({a.get('source', '?')}): {u}")
        return "Content for this conversation:\n" + "\n".join(lines)
    except Exception as e:
        return f"Failed to list assets: {str(e)}"


@tool
def suggest_caption_hashtags(
    tenant_id: str,
    conversation_id: str,
    content_description: str = "",
    platform: str = "tiktok",
    user_feedback: Optional[str] = None,
) -> str:
    """
    Suggest a caption and hashtags for the user's content based on vision analysis.
    Optionally incorporate user feedback. Use this before asking for confirmation to post.
    Store the suggestion in conversation state.
    
    Args:
        tenant_id: Tenant ID
        conversation_id: Conversation ID
        content_description: Optional fallback description (used if vision analysis unavailable)
        platform: Target platform (tiktok, facebook)
        user_feedback: Optional feedback from user to refine the suggestion
    
    Returns:
        JSON string with keys: caption, hashtags (list). Also persisted to conversation state.
    """
    try:
        # Get conversation to find pending asset
        async def _get_conv_and_asset(session):
            conv = await get_conversation(session, conversation_id, tenant_id)
            asset = None
            if conv and conv.pending_asset_id:
                asset = await get_asset(session, conv.pending_asset_id, tenant_id)
            return conv, asset

        conv, asset = asyncio.run(run_with_db_session(_get_conv_and_asset))

        # Use vision_analysis from asset if available, otherwise fall back
        visual_description = ""
        if asset and asset.vision_analysis:
            visual_description = asset.vision_analysis
        elif asset:
            # Try to analyze on the fly if we have URL but no analysis
            content_url = asset.s3_url or asset.external_url
            if content_url:
                try:
                    visual_description = analyze_content(content_url, asset_type=asset.asset_type)
                    # Save it for future use
                    if visual_description and not visual_description.startswith("Visual analysis"):
                        async def _update_vision(s):
                            await update_asset_vision_analysis(s, asset.id, tenant_id, visual_description)
                        asyncio.run(run_with_db_session(_update_vision))
                except Exception:
                    pass

        # Use visual description if available, otherwise fall back to content_description
        content_info = visual_description if visual_description else content_description
        if not content_info:
            content_info = "Content to be posted"

        system = """You suggest ONE caption and up to 10 hashtags for social media posts based on the visual content analysis.
Do not invent platform features. Be concise. Caption under 150 characters for TikTok.
Output ONLY valid JSON: {"caption": "...", "hashtags": ["a","b",...]}.
No markdown, no explanation."""

        prompt = f"Visual content analysis: {content_info}. Platform: {platform}."
        if user_feedback:
            prompt += f" User feedback: {user_feedback}."
        prompt += "\nSuggest caption and hashtags based on the visual content. Output only JSON."

        raw = _call_llm(prompt, system)
        # Strip code blocks if present
        raw = re.sub(r"^```\w*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw)
        raw = raw.strip()
        obj = json.loads(raw)
        caption = str(obj.get("caption") or "")[:150]
        tags = obj.get("hashtags")
        if not isinstance(tags, list):
            tags = []
        hashtags = [str(t).strip().lstrip("#") for t in tags if t][:10]

        async def _save(session):
            await update_conversation_state(
                session, conversation_id, tenant_id,
                suggested_caption=caption,
                suggested_hashtags=hashtags,
            )

        asyncio.run(run_with_db_session(_save))
        return json.dumps({"caption": caption, "hashtags": hashtags})
    except Exception as e:
        return json.dumps({"caption": "", "hashtags": [], "error": str(e)})
