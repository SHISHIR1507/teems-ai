"""
UGC generation endpoints
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from langsmith import traceable
import langsmith
from langsmith import Client
from typing import Optional
import os
import uuid
import re
from datetime import datetime
from crewai import Task, Crew

from app.core.dependencies import get_db_session
from app.core.config import LANGCHAIN_PROJECT
from app.models.schemas import ChatResponse, ScriptRequest, ScriptVideoResponse
from app.services import db_helpers
from app.services.s3_utils import upload_bytes_to_s3, get_s3_key_for_upload
from app.orchestrator.ugc_orchestrator import generate_ugc_with_orchestrator, chat_with_agent
from app.agents.script_agent import create_script_agent
from app.agents.audio_video_agent import create_audio_video_agent
from app.tools.audio_maker import AVATAR_VOICE_MAP

router = APIRouter()
# Initialize LangSmith client with error handling
try:
    langsmith_client = Client()
except Exception as e:
    print(f"Warning: Failed to initialize LangSmith client: {e}. LangSmith features will be disabled.")
    langsmith_client = None


@router.post("/upload", response_model=ChatResponse)
@traceable(name="chat_ugc_upload_endpoint", tags=["fastapi", "ugc-generation"])
async def chat_ugc_upload_endpoint(
    message: str = Form(...),
    person_image: Optional[UploadFile] = File(None),
    product_image: Optional[UploadFile] = File(None),
    conversation_id: Optional[str] = Form(None),
    session: AsyncSession = Depends(get_db_session)
):
    """Upload images and generate UGC with DB & S3 storage (NO local temp files)"""
    conversation_id = conversation_id or str(uuid.uuid4())
    
    # Get or create conversation
    conversation = await db_helpers.get_conversation(session, conversation_id)
    if not conversation:
        conversation = await db_helpers.create_conversation(session, conversation_id)
    
    # Add user message to database
    await db_helpers.add_message(session, conversation_id, "user", message)
    
    person_image_s3_url = None
    product_image_s3_url = None
    
    # Upload person image to S3 if provided (public-read for AI/ML API access)
    if person_image:
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
            session, conversation_id, "uploaded_person", person_image_s3_url,
            person_image.filename, {"size": len(content)}
        )
        print(f"✅ Person image uploaded to S3: {person_image_s3_url}")
    
    # Upload product image to S3 if provided (public-read for AI/ML API access)
    if product_image:
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
            session, conversation_id, "uploaded_product", product_image_s3_url,
            product_image.filename, {"size": len(content)}
        )
        print(f"✅ Product image uploaded to S3: {product_image_s3_url}")
    
    run_tree = langsmith.get_current_run_tree()
    
    try:
        # Get brand context
        brand_context = None
        if conversation.brand_locked:
            brand_context = {
                "industry": conversation.brand_industry,
                "audience": conversation.brand_audience,
                "vibe": conversation.brand_vibe,
                "locked": True
            }
        
        # Check if user wants to generate images
        if person_image_s3_url and product_image_s3_url:
            # Check if brand is locked
            if not brand_context or not brand_context.get('locked'):
                result = chat_with_agent(
                    "User wants to generate images but hasn't synced brand context yet. Guide them to complete brand sync first.",
                    brand_context=brand_context
                )
                assistant_message = str(result)
                steps = [{"type": "guidance", "description": "Brand sync required", "timestamp": datetime.now().isoformat()}]
                
                await db_helpers.add_message(session, conversation_id, "assistant", assistant_message)
                
                return ChatResponse(
                    conversation_id=conversation_id,
                    assistant_message=assistant_message,
                    steps=steps,
                    generated_images=None,
                    timestamp=datetime.now().isoformat(),
                    trace_url=None
                )
            
            # Brand is locked - proceed with generation using S3 URLs directly
            print(f"\n{'='*60}")
            print(f"Processing UGC generation: {conversation_id}")
            print(f"Using S3 URLs directly (no temp files)")
            print(f"{'='*60}\n")
            
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
            
            # Extract data from structured response
            assistant_message = result.get("message", str(result))
            generated_s3_urls = result.get("generated_images", [])
        else:
            # No images - use chat agent
            result = chat_with_agent(message, brand_context=brand_context)
            assistant_message = str(result)
            generated_s3_urls = []
        
        steps = [{"type": "agent_thinking", "description": "GPT-5 agent analyzed request", "timestamp": datetime.now().isoformat()}]
        
        # Store S3 URLs in database
        for idx, s3_url in enumerate(generated_s3_urls, start=1):
            await db_helpers.add_asset(
                session=session,
                conversation_id=conversation_id,
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
        await db_helpers.add_message(session, conversation_id, "assistant", assistant_message)
        
        # Get trace URL
        trace_url = None
        if run_tree and run_tree.id and langsmith_client:
            try:
                tenant_id = langsmith_client._get_tenant_id()
                project_name = os.getenv("LANGCHAIN_PROJECT", LANGCHAIN_PROJECT)
                trace_url = f"https://smith.langchain.com/o/{tenant_id}/projects/p/{project_name}/r/{run_tree.id}"
            except:
                pass
        
        return ChatResponse(
            conversation_id=conversation_id,
            assistant_message=assistant_message,
            steps=steps,
            generated_images=generated_s3_urls if generated_s3_urls else None,
            timestamp=datetime.now().isoformat(),
            trace_url=trace_url
        )
    
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.post("/script", response_model=ScriptVideoResponse)
@traceable(name="generate_script_audio_video_endpoint", tags=["fastapi", "script-audio-video"])
async def generate_script_and_video(
    request: ScriptRequest,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Generate UGC script, audio, and video (2-agent sequential workflow)
    Works with S3 URLs or local paths
    """
    conversation_id = request.conversation_id or str(uuid.uuid4())
    
    # Get or create conversation
    conversation = await db_helpers.get_conversation(session, conversation_id)
    if not conversation:
        conversation = await db_helpers.create_conversation(session, conversation_id)
    
    # Add user message
    await db_helpers.add_message(
        session, conversation_id, "user",
        f"Generate script, audio, and video for {request.ugc_image_path}"
    )
    
    run_tree = langsmith.get_current_run_tree()
    
    try:
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
            raise HTTPException(status_code=400, detail="Brand context must be synced before generating scripts")
        
        industry = brand_context.get('industry')
        audience = brand_context.get('audience')
        vibe = brand_context.get('vibe')
        voice_name = AVATAR_VOICE_MAP.get(request.avatar_id, "Harry")
        
        print(f"\n{'='*60}")
        print(f"Starting 2-Agent Workflow: Script → Audio+Video")
        print(f"Image: {request.ugc_image_path}")
        print(f"{'='*60}\n")
        
        # ============================================================
        # STEP 1: Generate Script (Dialogue + Video Script)
        # ============================================================
        print("STEP 1/2: Generating Script...")
        script_agent = create_script_agent()
        
        task1 = Task(
            description=f"""Generate an 8-second UGC video script with dialogue.

Brand context (LOCKED):
- Industry: {industry}
- Audience: {audience}
- Vibe: {vibe}

Call the "UGC Script Maker" tool with these parameters:
- ugc_image_reference: {request.ugc_image_path}
- product_name: {request.product_name}
- tone: {request.tone}
- platform: {request.platform}
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
        script_result = crew1.kickoff()
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
        
        # ============================================================
        # STEP 2: Generate Audio + Video (Single Agent)
        # ============================================================
        print("\nSTEP 2/2: Generating Audio + Video...")
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
- avatar_id: {request.avatar_id}
- output_filename: {audio_filename}
- conversation_id: {conversation_id}

STEP 2: Call "Veo3.1 Image-to-Video Generator" tool with:
- image_reference: {request.ugc_image_path}
- script_text: {video_script}
- duration_seconds: 8

Return both the audio S3 URL and video URL.""",
            expected_output="Audio S3 URL and Video URL",
            agent=audio_video_agent,
            human_input=False
        )
        
        crew2 = Crew(agents=[audio_video_agent], tasks=[task2], verbose=True, process="sequential")
        audio_video_result = crew2.kickoff()
        audio_video_result_str = str(audio_video_result)
        
        # Extract S3 URL from audio result
        audio_s3_url = None
        if "https://teems-agents.s3" in audio_video_result_str:
            urls = re.findall(r'https://teems-agents\.s3[^\s<>"{}|\\^`\[\]]+', audio_video_result_str)
            if urls:
                audio_s3_url = urls[0]
                print(f"✅ Audio Generated: {audio_s3_url}")
                
                # Store in database
                await db_helpers.add_asset(
                    session, conversation_id, "audio", audio_s3_url,
                    audio_filename, {"voice": voice_name, "avatar_id": request.avatar_id}
                )
        
        # Extract video URL
        video_url = None
        if "Success! Output URL:" in audio_video_result_str or "https://cdn.aimlapi.com" in audio_video_result_str:
            urls = re.findall(r'https://cdn\.aimlapi\.com[^\s<>"{}|\\^`\[\]]+', audio_video_result_str)
            if not urls:
                urls = re.findall(r'https://[^\s<>"{}|\\^`\[\]]+\.mp4[^\s<>"{}|\\^`\[\]]*', audio_video_result_str)
            if urls:
                video_url = urls[0]
                print(f"✅ Video Generated: {video_url}")
                
                # Store in database
                await db_helpers.add_asset(
                    session, conversation_id, "video", video_url,
                    f"video_{conversation_id}.mp4", {"duration": 8, "platform": request.platform}
                )
        
        # Get trace URL
        trace_url = None
        if run_tree and run_tree.id and langsmith_client:
            try:
                tenant_id = langsmith_client._get_tenant_id()
                project_name = os.getenv("LANGCHAIN_PROJECT", LANGCHAIN_PROJECT)
                trace_url = f"https://smith.langchain.com/o/{tenant_id}/projects/p/{project_name}/r/{run_tree.id}"
            except:
                pass
        
        print(f"\n{'='*60}")
        print(f"✅ Complete! Audio: {audio_s3_url is not None}, Video: {video_url is not None}")
        print(f"{'='*60}\n")
        
        return ScriptVideoResponse(
            conversation_id=conversation_id,
            script=video_script,
            dialogue=dialogue,
            audio_url=audio_s3_url,
            video_url=video_url,
            ugc_image_path=request.ugc_image_path,
            avatar_id=request.avatar_id,
            voice_used=voice_name,
            timestamp=datetime.now().isoformat(),
            trace_url=trace_url
        )
        
    except Exception as e:
        print(f"Error in script/audio/video generation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
