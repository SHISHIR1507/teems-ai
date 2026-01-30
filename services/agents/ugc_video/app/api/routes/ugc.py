"""
UGC generation endpoints
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
import sys
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor

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
from langsmith import traceable
import langsmith
from langsmith import Client
from typing import Optional
import os
import re
from datetime import datetime
from crewai import Task, Crew

from app.core.dependencies import get_db_session
from app.core.auth import AuthenticatedUser, require_tenant
from app.core.config import LANGCHAIN_PROJECT
from app.models.schemas import ChatResponse, ScriptRequest, ScriptVideoResponse
from app.services import db_helpers
from app.services.s3_utils import upload_bytes_to_s3, get_s3_key_for_upload
from app.services.realtime_notifier import (
    notify_job_started,
    notify_job_progress,
    notify_job_completed,
    notify_job_error
)
from app.orchestrator.ugc_orchestrator import generate_ugc_with_orchestrator, chat_with_agent
from app.agents.script_agent import create_script_agent
from app.agents.audio_video_agent import create_audio_video_agent
from app.agents.lipsync_agent import create_lipsync_agent
from app.tools.audio_maker import AVATAR_VOICE_MAP
from app.config.avatars import get_avatar_s3_url, avatar_exists

router = APIRouter()
# Initialize LangSmith client with error handling
try:
    langsmith_client = Client()
except Exception as e:
    print(f"Warning: Failed to initialize LangSmith client: {e}. LangSmith features will be disabled.")
    langsmith_client = None


@router.post("/v1/ugc/upload", response_model=ChatResponse, tags=["ugc"])
@traceable(name="chat_ugc_upload_endpoint", tags=["fastapi", "ugc-generation"])
async def chat_ugc_upload_endpoint(
    message: str = Form(...),
    person_image: Optional[UploadFile] = File(None),
    product_image: Optional[UploadFile] = File(None),
    avatar_id: Optional[int] = Form(None),
    conversation_id: Optional[str] = Form(None),
    regenerate: Optional[bool] = Form(False),
    product_name: Optional[str] = Form(None),
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Upload images and generate UGC with DB & S3 storage (NO local temp files)
    
    Supports two modes:
    1. Avatar mode: Provide avatar_id (1-9) to use predefined avatar image
    2. Custom mode: Upload person_image for custom person image
    
    Note: Cannot provide both avatar_id and person_image simultaneously.
    
    Regenerate mode: Set regenerate=true to trigger re-generation with existing images from state
    
    Requires authentication with tenant_id.
    """
    try:
        tenant_id = user.tenant_id
        user_id = user.sub
        conversation_id = resolve_conversation_id(conversation_id)
        
        # Validation: Cannot provide both avatar_id and person_image
        if avatar_id is not None and person_image is not None:
            raise_standard_error(
                status_code=400,
                message="Invalid request",
                detail="Cannot provide both avatar_id and person_image. Please provide only one."
            )
        
        # Get or create conversation with tenant isolation
        conversation = await db_helpers.get_or_create_conversation(
            session, conversation_id, tenant_id, user_id
        )
        
        # Add user message to database
        await db_helpers.add_message(session, conversation_id, tenant_id, "user", message)
        
        # Update product name if provided
        if product_name:
            await db_helpers.update_product_name(session, conversation_id, tenant_id, product_name)
            print(f"✅ Product name updated: {product_name}")
        
        person_image_s3_url = None
        product_image_s3_url = None
        
        # Handle avatar_id or person_image
        if avatar_id is not None:
            # Validate avatar_id
            if not avatar_exists(avatar_id):
                raise_standard_error(
                    status_code=400,
                    message="Invalid avatar ID",
                    detail=f"Avatar ID {avatar_id} does not exist. Valid IDs are 1-9."
                )
            
            # Get predefined avatar S3 URL
            person_image_s3_url = get_avatar_s3_url(avatar_id)
            print(f"✅ Using predefined avatar {avatar_id}: {person_image_s3_url}")
            
            # Save avatar usage to database
            await db_helpers.add_asset(
                session, conversation_id, tenant_id, user_id, "avatar_used", person_image_s3_url,
                f"avatar_{avatar_id}.jpg", {"avatar_id": avatar_id}
            )
            
        elif person_image:
            # Upload custom person image to S3 if provided (public-read for AI/ML API access)
            await notify_job_progress(
                tenant_id,
                conversation_id,
                "ugc_image_generation",
                {"step": "uploading_images", "progress": 5},
                "Uploading images to S3..."
            )
            content = await person_image.read()
            s3_key = get_s3_key_for_upload(conversation_id, person_image.filename, "person")
            person_image_s3_url = upload_bytes_to_s3(
                content, 
                s3_key, 
                person_image.content_type or "image/jpeg",
                public_read=True  # Make public for AI/ML API to access
            )
            
            # Save to database
            await db_helpers.add_asset(
                session, conversation_id, tenant_id, user_id, "uploaded_person", person_image_s3_url,
                person_image.filename, {"size": len(content)}
            )
            print(f"✅ Person image uploaded to S3: {person_image_s3_url}")
        
        # Upload product image to S3 if provided (public-read for AI/ML API access)
        if product_image:
            if avatar_id is None and person_image is None:
                # Notify progress if we're uploading images
                await notify_job_progress(
                    tenant_id,
                    conversation_id,
                    "ugc_image_generation",
                    {"step": "uploading_images", "progress": 5},
                    "Uploading images to S3..."
                )
            content = await product_image.read()
            s3_key = get_s3_key_for_upload(conversation_id, product_image.filename, "product")
            product_image_s3_url = upload_bytes_to_s3(
                content, 
                s3_key, 
                product_image.content_type or "image/jpeg",
                public_read=True  # Make public for AI/ML API to access
            )
            
            # Save to database
            await db_helpers.add_asset(
                session, conversation_id, tenant_id, user_id, "uploaded_product", product_image_s3_url,
                product_image.filename, {"size": len(content)}
            )
            print(f"✅ Product image uploaded to S3: {product_image_s3_url}")
        
        run_tree = langsmith.get_current_run_tree()
        
        # Get brand context
        brand_context = None
        if conversation.brand_locked:
            brand_context = {
                "industry": conversation.brand_industry,
                "audience": conversation.brand_audience,
                "vibe": conversation.brand_vibe,
                "locked": True
            }
        
        # Get conversation state for agent context (initial state)
        conversation_state_data = await db_helpers.get_conversation_state(
            session, conversation_id, tenant_id
        )
        
        # Get conversation history for agent context
        messages = await db_helpers.get_messages(session, conversation_id, tenant_id)
        conversation_history = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        # Determine if we should generate images
        # Priority 1: New uploads in this request
        has_new_uploads = person_image_s3_url and product_image_s3_url
        
        # Priority 2: Regenerate flag is set (user clicked regenerate button)
        # Only allow if we have existing images in state
        can_regenerate = (
            regenerate and
            not has_new_uploads and
            conversation_state_data and
            conversation_state_data.get('has_person') and
            conversation_state_data.get('has_product') and
            brand_context and brand_context.get('locked')
        )
        
        # Priority 3: First-time generation (auto-trigger when ready)
        # User has uploaded images, brand is synced, but hasn't generated yet
        is_first_generation = (
            not has_new_uploads and
            not regenerate and
            conversation_state_data and
            conversation_state_data.get('has_person') and
            conversation_state_data.get('has_product') and
            conversation_state_data.get('brand_locked') and
            not conversation_state_data.get('has_generated_images') and
            conversation_state_data.get('next_step') == 'generate_ugc_images'
        )
        
        # Determine if we should trigger generation
        should_generate = has_new_uploads or can_regenerate or is_first_generation
        
        # If regenerating or first generation, retrieve images from state
        if (can_regenerate or is_first_generation) and not has_new_uploads:
            person_image_s3_url = conversation_state_data.get('person_url')
            product_image_s3_url = conversation_state_data.get('product_url')
            
            # If user provided a new avatar_id, use that instead of the stored person_url
            if avatar_id is not None and avatar_id != conversation_state_data.get('avatar_id'):
                if avatar_exists(avatar_id):
                    person_image_s3_url = get_avatar_s3_url(avatar_id)
                    print(f"✅ Using NEW avatar {avatar_id} for re-generation: {person_image_s3_url}")
                else:
                    print(f"⚠️ Invalid avatar ID {avatar_id}, using existing person image")
            
            if is_first_generation:
                print(f"✅ First-time generation triggered: person={person_image_s3_url}, product={product_image_s3_url}")
            else:
                print(f"✅ Regenerating with existing images from state: person={person_image_s3_url}, product={product_image_s3_url}")
        
        # Build context message for agent about avatar usage
        avatar_context = ""
        if avatar_id is not None:
            avatar_context = f"\n\nIMPORTANT: User has selected Avatar ID {avatar_id} as their person image. Do NOT ask them to upload a person image."
        elif conversation_state_data and conversation_state_data.get("avatar_id"):
            avatar_context = f"\n\nIMPORTANT: User has already selected Avatar ID {conversation_state_data.get('avatar_id')} as their person image. Do NOT ask them to upload a person image."
        
        # Check if user wants to generate images
        if should_generate and person_image_s3_url and product_image_s3_url:
            # Check if brand is locked
            if not brand_context or not brand_context.get('locked'):
                result = chat_with_agent(
                    message=f"User wants to generate images but brand is not synced. Ask them directly for: 1) Industry, 2) Target audience, 3) Brand vibe, 4) Product name. Once you have all four, sync it immediately using the Brand Sync tool.{avatar_context}",
                    brand_context=brand_context,
                    conversation_id=conversation_id,
                    tenant_id=tenant_id,
                    enable_brand_sync=True,
                    conversation_state=conversation_state_data,
                    conversation_history=conversation_history
                )
                assistant_message = str(result)
                steps = [{"type": "guidance", "description": "Brand sync required", "timestamp": datetime.now().isoformat()}]
                
                await db_helpers.add_message(session, conversation_id, tenant_id, "assistant", assistant_message)
                
                return ChatResponse(
                    conversation_id=conversation_id,
                    assistant_message=assistant_message,
                    steps=steps,
                    generated_images=None,
                    timestamp=datetime.now().isoformat(),
                    trace_url=None
                )
            
            # Notify job started for image generation
            await notify_job_started(
                tenant_id,
                conversation_id,
                "ugc_image_generation",
                {
                    "message": message,
                    "has_images": True,
                    "brand_context": brand_context
                }
            )
            
            # Brand is locked - proceed with generation using S3 URLs directly
            print(f"\n{'='*60}")
            print(f"Processing UGC generation: {conversation_id}")
            print(f"Using S3 URLs directly (no temp files)")
            print(f"{'='*60}\n")
            
            # Notify progress: generating prompts
            await notify_job_progress(
                tenant_id,
                conversation_id,
                "ugc_image_generation",
                {"step": "generating_prompts", "progress": 30},
                "Analyzing images and generating prompts..."
            )
            
            # Call orchestrator with S3 URLs (NO temp files!)
            result = generate_ugc_with_orchestrator(
                person_image_url=person_image_s3_url,  # Pass S3 URL directly
                product_image_url=product_image_s3_url,  # Pass S3 URL directly
                base_intent=message,
                industry=brand_context.get('industry'),
                audience=brand_context.get('audience'),
                vibe=brand_context.get('vibe'),
                conversation_id=conversation_id,
                upload_to_s3=True  # Enable S3 upload for generated images
            )
            
            # Debug: Print what we received from orchestrator
            print(f"\n{'='*60}")
            print(f"DEBUG: Orchestrator Response")
            print(f"{'='*60}")
            print(f"Type: {type(result)}")
            print(f"Keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
            if isinstance(result, dict):
                print(f"Message length: {len(result.get('message', ''))}")
                print(f"Generated images: {result.get('generated_images', [])}")
                print(f"Number of images: {len(result.get('generated_images', []))}")
            print(f"{'='*60}\n")
            
            # Notify progress: generating images
            await notify_job_progress(
                tenant_id,
                conversation_id,
                "ugc_image_generation",
                {"step": "generating_images", "progress": 60},
                "Generating 4 UGC image variants..."
            )
            
            # Extract data from structured response
            assistant_message = result.get("message", str(result))
            generated_s3_urls = result.get("generated_images", [])
        else:
            # No images - use chat agent with brand sync enabled
            result = chat_with_agent(
                message + avatar_context,
                brand_context=brand_context,
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                enable_brand_sync=True,
                conversation_state=conversation_state_data,
                conversation_history=conversation_history
            )
            assistant_message = str(result)
            generated_s3_urls = []
        
        steps = [{"type": "agent_thinking", "description": "GPT-5 agent analyzed request", "timestamp": datetime.now().isoformat()}]
        
        # Store S3 URLs in database
        for idx, s3_url in enumerate(generated_s3_urls, start=1):
            await db_helpers.add_asset(
                session=session,
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                user_id=user_id,
                asset_type="generated_image",
                url=s3_url,
                filename=f"variant_{idx}.png",
                metadata={
                    "variant_index": idx,
                    "source": "banana_tool"
                }
            )
        
        if generated_s3_urls:
            steps.append({
                "type": "tool_call",
                "tool": "Banana UGC Generator",
                "description": f"Generated {len(generated_s3_urls)} UGC images and uploaded to S3",
                "timestamp": datetime.now().isoformat()
            })
        
        # Add assistant message to database
        await db_helpers.add_message(session, conversation_id, tenant_id, "assistant", assistant_message)
        
        # Commit all changes to database
        await session.commit()
        
        # Get FRESH conversation state after all operations (reflects brand sync, uploads, generations)
        from app.models.schemas import ConversationState
        fresh_state_data = await db_helpers.get_conversation_state(
            session, conversation_id, tenant_id
        )
        conversation_state = ConversationState(**fresh_state_data) if fresh_state_data else None
        
        # Determine if we should show regenerate button
        show_regenerate_button = (
            conversation_state and 
            conversation_state.has_generated_images and
            conversation_state.next_step == "regenerate_or_video"
        )
        
        # Get trace URL
        trace_url = None
        if run_tree and run_tree.id and langsmith_client:
            try:
                tenant_id_ls = langsmith_client._get_tenant_id()
                project_name = os.getenv("LANGCHAIN_PROJECT", LANGCHAIN_PROJECT)
                trace_url = f"https://smith.langchain.com/o/{tenant_id_ls}/projects/p/{project_name}/r/{run_tree.id}"
            except:
                pass
        
        # Notify job completed if images were generated
        if generated_s3_urls:
            await notify_job_completed(
                tenant_id,
                conversation_id,
                "ugc_image_generation",
                {
                    "generated_images": generated_s3_urls,
                    "count": len(generated_s3_urls),
                    "trace_url": trace_url
                }
            )
        
        return ChatResponse(
            conversation_id=conversation_id,
            assistant_message=assistant_message,
            steps=steps,
            generated_images=generated_s3_urls if generated_s3_urls else None,
            conversation_state=conversation_state,
            show_regenerate_button=show_regenerate_button,
            timestamp=datetime.now().isoformat(),
            trace_url=trace_url
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {str(e)}")
        # Notify error
        try:
            await notify_job_error(
                tenant_id,
                conversation_id,
                "ugc_image_generation",
                str(e),
                {"error_type": type(e).__name__}
            )
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/v1/ugc/script", response_model=ScriptVideoResponse, tags=["ugc"])
@traceable(name="generate_script_audio_video_endpoint", tags=["fastapi", "script-audio-video"])
async def generate_script_and_video(
    request: ScriptRequest,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Generate UGC script, audio, and video (3-agent sequential workflow)
    Works with S3 URLs or local paths
    
    Requires authentication with tenant_id.
    Brand context must be synced before generating scripts.
    """
    try:
        tenant_id = user.tenant_id
        user_id = user.sub
        conversation_id = resolve_conversation_id(request.conversation_id)
        
        # Get or create conversation with tenant isolation
        conversation = await db_helpers.get_or_create_conversation(
            session, conversation_id, tenant_id, user_id
        )
        
        # Verify ownership
        if not await db_helpers.verify_conversation_ownership(session, conversation_id, tenant_id):
            raise_standard_error(
                status_code=403,
                message="Access denied",
                detail="Access denied to this conversation"
            )
        
        # Get conversation state to retrieve avatar_id if not provided
        conversation_state = await db_helpers.get_conversation_state(
            session, conversation_id, tenant_id
        )
        
        # Retrieve product_name from conversation if not provided in request
        product_name = request.product_name
        if not product_name:
            product_name = conversation.product_name if hasattr(conversation, 'product_name') else None
        
        # Retrieve avatar_id from conversation state if not provided in request
        avatar_id = request.avatar_id
        if not avatar_id and conversation_state:
            avatar_id = conversation_state.get('avatar_id')
        
        # Validate that we have all required data
        if not product_name:
            raise_standard_error(
                status_code=400,
                message="Product name required",
                detail="Product name must be provided in request or synced via brand sync"
            )
        
        if not avatar_id:
            raise_standard_error(
                status_code=400,
                message="Avatar ID required",
                detail="Avatar ID must be provided in request or selected in conversation"
            )
        
        # Use defaults for tone and platform
        tone = request.tone or "energetic and authentic"
        platform = request.platform or "Instagram"
        
        print(f"\n{'='*60}")
        print(f"Script Generation Request")
        print(f"Product: {product_name}")
        print(f"Avatar ID: {avatar_id}")
        print(f"Tone: {tone}")
        print(f"Platform: {platform}")
        print(f"{'='*60}\n")
        
        # Add user message
        await db_helpers.add_message(
            session, conversation_id, tenant_id, "user",
            f"Generate script, audio, and video for {request.ugc_image_path}"
        )
        
        run_tree = langsmith.get_current_run_tree()
        
        # Get brand context
        brand_context = None
        if conversation.brand_locked:
            brand_context = {
                "industry": conversation.brand_industry,
                "audience": conversation.brand_audience,
                "vibe": conversation.brand_vibe,
                "locked": True
            }
        
        # Check if brand is locked
        if not brand_context or not brand_context.get('locked'):
            raise_standard_error(
                status_code=400,
                message="Brand context required",
                detail="Brand context must be synced before generating scripts. Please sync brand context first."
            )
        
        industry = brand_context.get('industry')
        audience = brand_context.get('audience')
        vibe = brand_context.get('vibe')
        
        # Get voice name from avatar mapping
        from app.config.avatars import get_avatar_voice_name
        voice_name = get_avatar_voice_name(avatar_id)
        
        # Fallback to legacy voice map if not found
        if not voice_name:
            voice_name = AVATAR_VOICE_MAP.get(avatar_id, "Harry")
            print(f"⚠️ Using legacy voice mapping: {voice_name}")
        else:
            print(f"✅ Using custom avatar voice: {voice_name} (Avatar ID: {avatar_id})")
        
        # Notify job started
        await notify_job_started(
            tenant_id,
            conversation_id,
            "script_audio_video",
            {
                "ugc_image_path": request.ugc_image_path,
                "product_name": product_name,
                "avatar_id": avatar_id,
                "platform": platform
            }
        )
        
        print(f"\n{'='*60}")
        print(f"Starting 3-Agent Workflow: Script → Audio+Video → Lipsync")
        print(f"Image: {request.ugc_image_path}")
        print(f"{'='*60}\n")
        
        # ============================================================
        # STEP 1: Generate Script (Dialogue + Video Script)
        # ============================================================
        print("STEP 1/3: Generating Script...")
        
        # Notify progress: generating script
        await notify_job_progress(
            tenant_id,
            conversation_id,
            "script_audio_video",
            {"step": "generating_script", "progress": 20},
            "Generating script and dialogue..."
        )
        
        script_agent = create_script_agent()
        
        task1 = Task(
            description=f"""Generate an 8-second UGC video script with dialogue.

Brand context (LOCKED):
- Industry: {industry}
- Audience: {audience}
- Vibe: {vibe}

Call the "UGC Script Maker" tool with these parameters:
- ugc_image_reference: {request.ugc_image_path}
- product_name: {product_name}
- tone: {tone}
- platform: {platform}
- industry: {industry}
- audience: {audience}
- vibe: {vibe}
- conversation_id: {conversation_id}

Return the complete output with both dialogue and video script.""",
            expected_output="Complete output with UGC dialogue and video script sections",
            agent=script_agent,
            human_input=False
        )
        
        crew1 = Crew(agents=[script_agent], tasks=[task1], verbose=True, process="sequential")
        loop = asyncio.get_event_loop()
        script_result = await loop.run_in_executor(ThreadPoolExecutor(), crew1.kickoff)
        script_result_str = str(script_result)
        
        # Parse dialogue and video script
        dialogue = ""
        video_script = ""
        
        if "=== UGC DIALOGUE ===" in script_result_str:
            parts = script_result_str.split("=== UGC DIALOGUE ===")
            if len(parts) > 1:
                dialogue = parts[1].split("=== VIDEO SCRIPT ===")[0].strip()
        
        if "=== VIDEO SCRIPT ===" in script_result_str:
            parts = script_result_str.split("=== VIDEO SCRIPT ===")
            if len(parts) > 1:
                video_script = parts[1].strip()
        
        print(f"✅ Script Generated! Dialogue: {len(dialogue)} chars, Script: {len(video_script)} chars")
        
        # Notify progress: generating audio
        await notify_job_progress(
            tenant_id,
            conversation_id,
            "script_audio_video",
            {"step": "generating_audio", "progress": 50},
            "Generating audio from dialogue..."
        )
        
        # ============================================================
        # STEP 2: Generate Audio + Video (Single Agent)
        # ============================================================
        print("\nSTEP 2/3: Generating Audio + Video...")
        audio_video_agent = create_audio_video_agent()
        audio_filename = f"ugc_audio_{conversation_id}.mp3"
        
        task2 = Task(
            description=f"""Generate audio and video for this UGC content.

DIALOGUE TEXT (for audio):
{dialogue}

VIDEO SCRIPT (for video):
{video_script}

IMAGE REFERENCE: {request.ugc_image_path}

STEP 1: Call "UGC Audio Generator" tool with:
- dialogue_text: {dialogue}
- avatar_id: {avatar_id}
- output_filename: {audio_filename}
- conversation_id: {conversation_id}

STEP 2: Call "Veo3.1 Image-to-Video Generator" tool with:
- image_reference: {request.ugc_image_path}
- script_text: {video_script}
- duration_seconds: 8
- tenant_id: {tenant_id}
- conversation_id: {conversation_id}

Return both the audio S3 URL and video URL.""",
            expected_output="Audio S3 URL and Video URL",
            agent=audio_video_agent,
            human_input=False
        )
        
        # Notify progress: generating video (this is the longest step)
        await notify_job_progress(
            tenant_id,
            conversation_id,
            "script_audio_video",
            {"step": "generating_video", "progress": 70},
            "Generating video (this may take 30-90 seconds)..."
        )
        
        crew2 = Crew(agents=[audio_video_agent], tasks=[task2], verbose=True, process="sequential")
        loop = asyncio.get_event_loop()
        audio_video_result = await loop.run_in_executor(ThreadPoolExecutor(), crew2.kickoff)
        audio_video_result_str = str(audio_video_result)
        
        print(f"\n{'='*60}")
        print(f"DEBUG: Audio/Video Agent Result")
        print(f"{'='*60}")
        print(f"Result length: {len(audio_video_result_str)} chars")
        print(f"Result preview: {audio_video_result_str[:500]}...")
        print(f"{'='*60}\n")
        
        # Extract S3 URL from audio result
        audio_s3_url = None
        if "https://teems-agents.s3" in audio_video_result_str:
            urls = re.findall(r'https://teems-agents\.s3[^\s<>"{}|\\^`\[\]]+', audio_video_result_str)
            if urls:
                audio_s3_url = urls[0]
                print(f"✅ Audio Generated: {audio_s3_url}")
                
                # Store in database
                await db_helpers.add_asset(
                    session, conversation_id, tenant_id, user_id, "audio", audio_s3_url,
                    audio_filename, {"voice": voice_name, "avatar_id": avatar_id}
                )
        
        if not audio_s3_url:
            print("⚠️  WARNING: Could not extract audio S3 URL from result")
        
        # Extract video URL - try multiple patterns
        video_url = None
        
        # Pattern 1: cdn.aimlapi.com URLs
        if "cdn.aimlapi.com" in audio_video_result_str:
            urls = re.findall(r'https://cdn\.aimlapi\.com[^\s<>"{}|\\^`\[\]]+', audio_video_result_str)
            if urls:
                video_url = urls[0]
        
        # Pattern 2: Any .mp4 URL
        if not video_url:
            urls = re.findall(r'https://[^\s<>"{}|\\^`\[\]]+\.mp4[^\s<>"{}|\\^`\[\]]*', audio_video_result_str)
            if urls:
                video_url = urls[0]
        
        if video_url:
            print(f"✅ Video Generated: {video_url}")
            
            # Store in database
            await db_helpers.add_asset(
                session, conversation_id, tenant_id, user_id, "video", video_url,
                f"video_{conversation_id}.mp4", {"duration": 8, "platform": platform}
            )
        else:
            print("⚠️  WARNING: Could not extract video URL from result")
        
        print(f"\n{'='*60}")
        print(f"Step 2 Complete - Checking for Step 3")
        print(f"Audio URL: {audio_s3_url is not None}")
        print(f"Video URL: {video_url is not None}")
        print(f"Will proceed to lipsync: {audio_s3_url is not None and video_url is not None}")
        print(f"{'='*60}\n")
        
        # ============================================================
        # STEP 3: Lipsync Audio + Video
        # ============================================================
        final_video_url = None
        
        if audio_s3_url and video_url:
            print("\nSTEP 3/3: Lipsyncing Audio + Video...")
            
            # Notify progress: lipsyncing
            await notify_job_progress(
                tenant_id,
                conversation_id,
                "script_audio_video",
                {"step": "lipsyncing", "progress": 85},
                "Syncing audio with video (this may take 30-60 seconds)..."
            )
            
            try:
                lipsync_agent = create_lipsync_agent()
                
                task3 = Task(
                    description=f"""Lipsync the audio with the video.

Call the "Lipsync Video Generator" tool with:
- video_url: {video_url}
- audio_url: {audio_s3_url}
- output_filename: final_ugc_{conversation_id}

Return the final lipsynced video URL.""",
                    expected_output="Final lipsynced video URL",
                    agent=lipsync_agent,
                    human_input=False
                )
                
                crew3 = Crew(agents=[lipsync_agent], tasks=[task3], verbose=True, process="sequential")
                loop = asyncio.get_event_loop()
                lipsync_result = await loop.run_in_executor(ThreadPoolExecutor(), crew3.kickoff)
                lipsync_result_str = str(lipsync_result)
                
                print(f"\n{'='*60}")
                print(f"DEBUG: Lipsync Agent Result")
                print(f"{'='*60}")
                print(f"Result: {lipsync_result_str}")
                print(f"{'='*60}\n")
                
                # Extract final video URL from lipsync result
                # Handle multiple URL patterns: storage.sync.so, api.sync.so/generations, or any .mp4
                if "Success! Output URL:" in lipsync_result_str or "https://" in lipsync_result_str:
                    # Try storage.sync.so URLs first (permanent storage)
                    urls = re.findall(r'https://storage\.sync\.so[^\s<>"{}|\\^`\[\]]+', lipsync_result_str)
                    
                    # Try api.sync.so generation URLs (temporary with token)
                    if not urls:
                        urls = re.findall(r'https://api\.sync\.so/v2/generations/[^\s<>"{}|\\^`\[\]]+', lipsync_result_str)
                    
                    # Try any .mp4 URLs as fallback
                    if not urls:
                        urls = re.findall(r'https://[^\s<>"{}|\\^`\[\]]+\.mp4[^\s<>"{}|\\^`\[\]]*', lipsync_result_str)
                    
                    if urls:
                        final_video_url = urls[0]
                        print(f"✅ Lipsync Complete: {final_video_url}")
                        
                        # Store final video in database
                        await db_helpers.add_asset(
                            session, conversation_id, tenant_id, user_id, "final_video", final_video_url,
                            f"final_ugc_{conversation_id}.mp4", 
                            {"duration": 8, "platform": platform, "lipsynced": True}
                        )
                    else:
                        print("⚠️  Lipsync completed but could not extract video URL from result")
                        print(f"Full result: {lipsync_result_str}")
                else:
                    print("⚠️  Lipsync did not complete successfully")
                    print(f"Result: {lipsync_result_str}")
            
            except Exception as e:
                print(f"❌ Error in lipsync step: {str(e)}")
                print("Continuing with non-lipsynced video...")
        else:
            print("\n⚠️  Skipping Step 3 (Lipsync) - Missing audio or video")
            print(f"   Audio URL present: {audio_s3_url is not None}")
            print(f"   Video URL present: {video_url is not None}")
        
        # Get trace URL
        trace_url = None
        if run_tree and run_tree.id and langsmith_client:
            try:
                tenant_id_ls = langsmith_client._get_tenant_id()
                project_name = os.getenv("LANGCHAIN_PROJECT", LANGCHAIN_PROJECT)
                trace_url = f"https://smith.langchain.com/o/{tenant_id_ls}/projects/p/{project_name}/r/{run_tree.id}"
            except:
                pass
        
        print(f"\n{'='*60}")
        print(f"✅ Complete! Audio: {audio_s3_url is not None}, Video: {video_url is not None}, Final: {final_video_url is not None}")
        print(f"{'='*60}\n")
        
        # Determine completion status
        current_step = "completed"
        progress_percentage = 100
        if not audio_s3_url and not video_url:
            current_step = "script"
            progress_percentage = 25
        elif audio_s3_url and not video_url:
            current_step = "audio"
            progress_percentage = 50
        elif audio_s3_url and video_url and not final_video_url:
            current_step = "video"
            progress_percentage = 75
        elif final_video_url:
            current_step = "completed"
            progress_percentage = 100
        
        # Notify job completed
        await notify_job_completed(
            tenant_id,
            conversation_id,
            "script_audio_video",
            {
                "script": video_script,
                "dialogue": dialogue,
                "audio_url": audio_s3_url,
                "video_url": video_url,
                "final_video_url": final_video_url,
                "voice_used": voice_name,
                "trace_url": trace_url
            }
        )
        
        return ScriptVideoResponse(
            conversation_id=conversation_id,
            script=video_script,
            dialogue=dialogue,
            audio_url=audio_s3_url,
            video_url=final_video_url if final_video_url else video_url,  # Return final lipsynced video if available
            ugc_image_path=request.ugc_image_path,
            avatar_id=avatar_id,
            voice_used=voice_name,
            timestamp=datetime.now().isoformat(),
            trace_url=trace_url,
            current_step=current_step,
            total_steps=3,
            progress_percentage=progress_percentage
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in script/audio/video generation: {str(e)}")
        # Notify error
        try:
            await notify_job_error(
                tenant_id,
                conversation_id,
                "script_audio_video",
                str(e),
                {"error_type": type(e).__name__}
            )
        except:
            pass
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )
