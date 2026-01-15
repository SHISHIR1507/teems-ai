import re
import requests
from fastapi import APIRouter, Form
from langsmith.run_helpers import get_current_run_tree
from app.services.session_service import get_or_create_session, update_session_history, SESSIONS
from app.services.vision_service import analyze_image
from app.services.agent_service import process_chat_message
from app.services.s3_service import upload_to_s3
from app.core.config import settings

router = APIRouter()

@router.post("/chat")
async def chat_endpoint(
    session_id: str = Form(...),
    message: str = Form(""),
):
    rt = get_current_run_tree()
    run_id = str(rt.id) if rt else None
    
    # Check if session is new (edge case - starting via chat)
    is_new_session = session_id not in SESSIONS
    session = get_or_create_session(session_id)
    
    # If new session and no message or empty message, show welcome
    if is_new_session and not message:
        return {
            "status": "success",
            "output": f"Welcome! Please select an avatar first.\n\nPreset Avatars:\n" + "\n".join(settings.PRESET_AVATARS)
        }
    
    # Get assets for context
    assets = session["avatars"] + session["apparel"]
    if session["generated"]:
        assets.append(session["generated"][-1])
    
    # Vision analysis if we have apparel
    visual_context = ""
    if session["apparel"]:
        desc = analyze_image(session["apparel"][-1])
        visual_context = f"VISUAL ANALYSIS OF APPAREL: {desc}"
    
    # History management
    history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in session["history"][-4:]])
    
    # Create agent and process message
    output_text = process_chat_message(
        message=message,
        session=session,
        assets=assets,
        visual_context=visual_context,
        history_text=history_text
    )
    
    # Extract and process generated URLs
    urls = re.findall(r'https?://[^\s\'"<>\]\)]+', output_text)
    new_gen_urls = []
    
    for url in urls:
        if url not in assets:
            try:
                if "aimlapi" in url or "d144" in url:
                    img_data = requests.get(url).content
                    s3_permanent_url = upload_to_s3(img_data, "ai_generated", "png")
                    new_gen_urls.append(s3_permanent_url)
                    output_text = output_text.replace(url, s3_permanent_url)
            except Exception as e:
                print(f"Failed to upload gen image to S3: {url}")
                new_gen_urls.append(url)
    
    if new_gen_urls:
        session["generated"].extend(new_gen_urls)
        session["stage"] = "GENERATION"
    
    # Update history
    update_session_history(session, message, output_text)
    
    return {
        "status": "success",
        "output": output_text,
        "run_id": run_id
    }
