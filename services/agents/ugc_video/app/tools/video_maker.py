"""
Veo-3.1 Image-to-Video Generator Tool for CrewAI
Converts: (image + script) -> Veo-3.1 Image-to-Video output
"""

import base64
import time
import requests
import asyncio
import threading
from typing import Type, Optional
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from app.core.config import AIML_API_KEY


class Veo3VideoMakerInput(BaseModel):
    """Input schema for Veo3 Video Generator."""
    image_reference: str = Field(
        ...,
        description="URL or local path to reference image for Veo-3 video conditioning"
    )
    script_text: str = Field(
        ...,
        description="The final structured script to turn into a video"
    )
    duration_seconds: int = Field(
        default=8,
        description="Desired video duration (default 8 seconds)"
    )
    tenant_id: Optional[str] = Field(
        default=None,
        description="Tenant ID for progress notifications (optional)"
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Conversation ID for progress notifications (optional)"
    )


class Veo3VideoMakerTool(BaseTool):
    name: str = "Veo3.1 Image-to-Video Generator"
    description: str = (
        "Converts a script + reference image into a generated video using "
        "Google Veo-3.1 Image-to-Video API."
    )
    args_schema: Type[BaseModel] = Veo3VideoMakerInput
    cache_function: bool = False

    def _get_image_url(self, path_or_url: str) -> str:
        """Converts local image to base64 data URI or returns URL directly."""
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return path_or_url
        
        # Read local file and convert to base64 data URI
        try:
            with open(path_or_url, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")
            
            # Determine MIME type from extension
            ext = path_or_url.lower().split('.')[-1]
            mime_map = {
                'png': 'image/png',
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'gif': 'image/gif',
                'webp': 'image/webp'
            }
            mime_type = mime_map.get(ext, 'image/png')
            
            return f"data:{mime_type};base64,{image_data}"
        except Exception as e:
            raise Exception(f"Error reading local image file: {str(e)}")

    def _run(
        self, 
        image_reference: str, 
        script_text: str, 
        duration_seconds: int,
        tenant_id: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> str:
        """Generate Veo-3.1 video from image + script."""

        if not AIML_API_KEY:
            return "Error: AIML_API_KEY environment variable not set"

        base_url = "https://api.aimlapi.com/v2"
        
        # Get image URL (converts local files to base64 data URI)
        try:
            image_url = self._get_image_url(image_reference)
        except Exception as e:
            return f"Error processing image: {str(e)}"

        # Step 1: Create video generation task
        headers = {
            "Authorization": f"Bearer {AIML_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "google/veo-3.1-i2v",
            "prompt": script_text,
            "image_url": image_url,
            "duration": duration_seconds,
            "aspect_ratio": "9:16",
            "resolution": "1080p",
            "generate_audio": False
        }

        try:
            # Submit generation request
            response = requests.post(
                f"{base_url}/video/generations",
                json=payload,
                headers=headers
            )
            
            if response.status_code >= 400:
                return f"Error submitting video generation: {response.status_code} - {response.text}"
            
            response_data = response.json()
            generation_id = response_data.get("id")
            
            if not generation_id:
                return f"Error: No generation ID returned. Response: {response_data}"
            
            print(f"Video generation started. ID: {generation_id}")
            
            # Step 2: Poll for completion with progress updates
            timeout = 300  # 5 minutes timeout
            start_time = time.time()
            last_progress_update = 0
            poll_count = 0
            
            while time.time() - start_time < timeout:
                check_response = requests.get(
                    f"{base_url}/video/generations",
                    params={"generation_id": generation_id},
                    headers=headers
                )
                
                if check_response.status_code >= 400:
                    return f"Error checking status: {check_response.status_code} - {check_response.text}"
                
                result = check_response.json()
                status = result.get("status")
                
                print(f"Status: {status}")
                
                # Send progress update every 10 seconds if tenant_id and conversation_id are provided
                elapsed = time.time() - start_time
                if tenant_id and conversation_id and elapsed - last_progress_update >= 10:
                    poll_count += 1
                    last_progress_update = elapsed
                    # Calculate progress: 70% base + up to 20% for polling (90% max before completion)
                    progress = min(90, 70 + int((elapsed / timeout) * 20))
                    
                    # Send async notification (non-blocking, fire-and-forget using background thread)
                    def send_notification():
                        """Send notification in background thread"""
                        try:
                            from app.services.realtime_notifier import notify_job_progress
                            # Create new event loop for this thread
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(notify_job_progress(
                                tenant_id,
                                conversation_id,
                                "video_generation",
                                {
                                    "step": "polling",
                                    "progress": progress,
                                    "elapsed_seconds": int(elapsed),
                                    "status": status,
                                    "poll_count": poll_count
                                },
                                f"Video generation in progress... ({status})"
                            ))
                            loop.close()
                        except Exception as e:
                            # Silently fail if notification doesn't work (non-critical)
                            print(f"Note: Could not send progress update: {e}")
                    
                    # Start notification in background thread (non-blocking)
                    thread = threading.Thread(target=send_notification, daemon=True)
                    thread.start()
                
                if status == "completed":
                    video_url = result.get("video", {}).get("url")
                    if video_url:
                        return f"✅ Video generated successfully: {video_url}\n\n[VIDEO_GENERATION_COMPLETE] - Task finished."
                    return f"Video completed but no URL found. Response: {result}"
                
                elif status == "failed":
                    error = result.get("error", "Unknown error")
                    return f"Video generation failed: {error}"
                
                elif status in ["waiting", "active", "queued", "generating"]:
                    time.sleep(10)
                else:
                    return f"Unknown status: {status}. Response: {result}"
            
            return f"Timeout: Video generation took longer than {timeout} seconds. Generation ID: {generation_id}"

        except Exception as e:
            return f"Error generating Veo-3.1 video: {str(e)}"
