"""
Chat router - AI chat interface powered by CrewAI
"""
import re
import uuid as _uuid
import requests
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
from langsmith.run_helpers import get_current_run_tree
from app.core.dependencies import get_db_session
from app.core.auth import AuthenticatedUser, require_tenant
from app.models.schemas import ChatRequest, ChatResponse
from app.orchestrator.fashion_orchestrator import chat_with_fashion_director
from app.services.db_helpers import (
    get_or_create_session,
    get_session,
    get_session_avatars,
    get_session_apparel,
    get_session_generated_images,
    get_session_messages,
    get_last_batch_id,
    add_message,
    update_session_stage,
    update_session_metadata,
    create_generated_image,
)
from app.services.s3_service import upload_to_s3
from app.services.realtime_notifier import (
    notify_image_generation_started,
    notify_image_generation_completed,
)
from app.tools.vision_tools import analyze_image
from app.core.config import get_settings
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger("routes.chat")


@router.post("/v1/chat", response_model=ChatResponse, tags=["chat"])
async def chat(
    request: ChatRequest,
    user: AuthenticatedUser = Depends(require_tenant()),
    db: AsyncSession = Depends(get_db_session),
) -> ChatResponse:
    """
    Chat with the Fashion Director. Workflow: apparel → avatar → scene → confirm → generate → edit.
    All conversation flows naturally; no manual anchors.
    """
    try:
        rt = get_current_run_tree()
        run_id = str(rt.id) if rt else None
        tenant_id = user.tenant_id
        session_id = request.session_id or str(_uuid.uuid4())

        fashion_session = await get_or_create_session(db, session_id, tenant_id, user.sub)

            if not request.message:
            settings = get_settings()
            welcome = (
                "Let's create some fashion photos. First, upload your apparel images "
                "(use the upload API with upload_type=apparel). Then we'll pick an avatar. "
                "Preset avatars you can use:\n" + "\n".join(settings.preset_avatars)
            )
            await add_message(db, session_id, tenant_id, "assistant", welcome)
            return ChatResponse(
                message=welcome,
                session_id=session_id,
                stage=fashion_session.stage,
                run_id=run_id,
                available_actions=["upload_apparel"],
                next_steps=["Upload apparel images to get started"]
            )

        await add_message(db, session_id, tenant_id, "user", request.message)

        avatars = await get_session_avatars(db, session_id, tenant_id)
        apparel = await get_session_apparel(db, session_id, tenant_id)
        generated = await get_session_generated_images(db, session_id, tenant_id, limit=50)
        last_batch_id = await get_last_batch_id(db, session_id, tenant_id)
        last_batch_images = await get_session_generated_images(
            db, session_id, tenant_id, limit=20, batch_id=last_batch_id
        ) if last_batch_id else []

        avatar_urls = [a.s3_url for a in avatars]
        apparel_urls = [a.s3_url for a in apparel]
        generated_urls = [img.s3_url for img in generated]
        last_batch_urls = [img.s3_url for img in last_batch_images]

        visual_parts = []
        if apparel:
            a0 = apparel[0]
            app_text = a0.vision_analysis or analyze_image(a0.s3_url, mode="apparel")
            visual_parts.append(f"APPAREL: {app_text}")
        if avatars:
            a0 = avatars[0]
            av_text = getattr(a0, "avatar_analysis", None) or analyze_image(a0.s3_url, mode="avatar")
            visual_parts.append(f"AVATAR: {av_text}")
        visual_context = "\n".join(visual_parts) if visual_parts else ""

        messages = await get_session_messages(db, session_id, limit=10)
        history_text = "\n".join(
            f"{m.role}: {m.content}" for m in reversed(list(messages)[:4])
        )

        suggested_scene = None
        if getattr(fashion_session, "metadata", None):
            suggested_scene = fashion_session.metadata.get("suggested_scene")

        output_text = chat_with_fashion_director(
            message=request.message,
            stage=fashion_session.stage,
            avatars=avatar_urls,
            apparel=apparel_urls,
            generated_images=generated_urls,
            history_text=history_text,
            visual_context=visual_context,
            suggested_scene=suggested_scene,
            last_batch_urls=last_batch_urls,
        )

        urls = re.findall(r'https?://[^\s\'"<>\]\)]+', output_text)
        new_gen_urls = []
        batch_id = None
        known = set(avatar_urls + apparel_urls + generated_urls)
        
        # Check if we have temp gen URLs (image generation detected)
        has_temp_gen = any(
            "aimlapi" in url or "d144" in url or "generated" in url.lower()
            for url in urls
            if url not in known
        )
        
        # Notify image generation started if we detect temp URLs
        if has_temp_gen:
            batch_id = str(_uuid.uuid4())
            # Extract scene description from suggested_scene or use default
            if suggested_scene and isinstance(suggested_scene, dict):
                scene_desc = suggested_scene.get("scene_description", "Fashion photography scene")
                angles_list = suggested_scene.get("angles", ["Front", "Side"])
                angles_count = len(angles_list) if isinstance(angles_list, list) else 2
                variations = suggested_scene.get("variations_per_angle", 2)
                variations = variations if isinstance(variations, int) else 2
            else:
                scene_desc = "Fashion photography scene"
                angles_count = 2
                variations = 2
            await notify_image_generation_started(
                tenant_id, session_id, batch_id, scene_desc, angles_count, variations
            )

        for url in urls:
            if url in known:
                continue
            is_temp_gen = "aimlapi" in url or "d144" in url or "generated" in url.lower()
            if not is_temp_gen:
                continue
            try:
                img_data = requests.get(url, timeout=30).content
                s3_url = upload_to_s3(img_data, "ai_generated", "png")
                s3_key = s3_url.split("/")[-1]
                if batch_id is None:
                    batch_id = str(_uuid.uuid4())
                    # Late notification if batch_id wasn't set earlier
                    if suggested_scene and isinstance(suggested_scene, dict):
                        scene_desc = suggested_scene.get("scene_description", "Fashion photography scene")
                    else:
                        scene_desc = "Fashion photography scene"
                    await notify_image_generation_started(
                        tenant_id, session_id, batch_id, scene_desc, 2, 2
                    )
                await create_generated_image(
                    db, session_id, tenant_id,
                    s3_url, s3_key, user.sub,
                    batch_id=batch_id,
                    generation_type="initial",
                )
                new_gen_urls.append(s3_url)
                output_text = output_text.replace(url, s3_url)
                known.add(s3_url)
            except Exception as e:
                logger.warning("Failed to fetch/upload gen image %s: %s", url, e)

        if new_gen_urls and batch_id:
            await update_session_metadata(
                db, session_id, tenant_id,
                {"last_generation_batch_id": batch_id},
            )
            # Notify completion
            await notify_image_generation_completed(
                tenant_id, session_id, batch_id, new_gen_urls, success=True
            )
        elif batch_id and not new_gen_urls:
            # Generation started but failed
            await notify_image_generation_completed(
                tenant_id, session_id, batch_id, [], success=False,
                error="Failed to generate or upload images"
            )
        if new_gen_urls and fashion_session.stage not in ("GENERATION", "EDITING"):
            await update_session_stage(db, session_id, tenant_id, "GENERATION")

        await add_message(db, session_id, tenant_id, "assistant", output_text)
        fashion_session = await get_session(db, session_id, tenant_id)
        
        # Determine available actions based on stage
        available_actions = []
        next_steps = []
        stage = fashion_session.stage
        
        if stage == "CONVERSATION" or stage == "APPAREL_SELECTION":
            available_actions = ["upload_apparel"]
            next_steps = ["Upload apparel images to get started"]
        elif stage == "AVATAR_SELECTION":
            available_actions = ["upload_avatar", "select_preset_avatar"]
            next_steps = ["Upload or select an avatar"]
        elif stage == "SCENE_SUGGESTION":
            available_actions = ["suggest_scenes", "describe_scene"]
            next_steps = ["Ask for scene suggestions or describe your desired scene"]
        elif stage == "GENERATION":
            available_actions = ["view_images", "edit_images", "regenerate"]
            next_steps = ["Review generated images", "Request edits or regenerate"]
        elif stage == "EDITING":
            available_actions = ["view_images", "regenerate", "download"]
            next_steps = ["Continue editing or download final images"]
        
        # Generation progress info if images are being generated
        generation_progress = None
        if has_temp_gen or batch_id:
            if new_gen_urls:
                generation_progress = {
                    "status": "completed",
                    "images_generated": len(new_gen_urls),
                    "total_expected": len(new_gen_urls)
                }
            else:
                generation_progress = {
                    "status": "processing",
                    "images_generated": 0,
                    "total_expected": 4,  # Default expectation
                    "estimated_time_seconds": 30
                }

        return ChatResponse(
            message=output_text,
            action_taken="image_generation" if new_gen_urls else "chat",
            session_id=session_id,
            stage=fashion_session.stage,
            image_urls=new_gen_urls if new_gen_urls else None,
            batch_id=batch_id,
            run_id=run_id,
            available_actions=available_actions,
            next_steps=next_steps,
            generation_progress=generation_progress
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Chat error")
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )
