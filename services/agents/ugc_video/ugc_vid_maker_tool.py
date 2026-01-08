"""
Veo-3.1 Image-to-Video Generator Tool for CrewAI
Converts: (image + script) -> Veo-3.1 Image-to-Video output
"""

import os
import base64
import time
import requests
from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from dotenv import load_dotenv

# Load .env variables
load_dotenv()


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

    def _run(self, image_reference: str, script_text: str, duration_seconds: int) -> str:
        """Generate Veo-3.1 video from image + script."""

        api_key = os.getenv("AIML_API_KEY")
        if not api_key:
            return "Error: AIML_API_KEY environment variable not set"

        base_url = "https://api.aimlapi.com/v2"
        
        # Get image URL (converts local files to base64 data URI)
        try:
            image_url = self._get_image_url(image_reference)
        except Exception as e:
            return f"Error processing image: {str(e)}"

        # Step 1: Create video generation task
        headers = {
            "Authorization": f"Bearer {api_key}",
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
            
            # Step 2: Poll for completion
            timeout = 300  # 5 minutes timeout
            start_time = time.time()
            
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


# Example direct run
if __name__ == "__main__":
    tool = Veo3VideoMakerTool()
    
    result = tool._run(
        image_reference="ugc_ea0bf77a-dc81-4770-b12e-403df1597d1f_20251223_160955_1.png",
        script_text='''FORMAT: Single continuous-shot UGC video script (silent, lip-sync only) for Instagram Stories
DURATION: 8 seconds
OUTPUT CONSTRAINT: One shot only; no cuts, no transitions, no on-screen text; continuous speech-mimicking lip motion for the full 0–8s
CAMERA: Medium close-up (chest to face), vertical 9:16, subtle handheld realism, fixed framing (no zoom/pan)
SUBJECT: Same creator, outfit, hair, and setting exactly as in the provided UGC image reference; calm, confident demeanor with steady eye contact

ACTION TIMELINE:
  0–8s: The creator faces the camera in the same position and environment as the reference image. They maintain steady eye contact and perform continuous, natural speech-mimicking lip motion for the entire line: “Quick trail break—my Red Bull’s keeping me steady for the last climb. Almost at the view.”
  - Throughout: Calm, conversational expression; slight head micro-nods timed to emphasis (“trail break,” “steady,” “last climb,” “Almost”).
  - One hand holds a partially visible redbull can at chest/torso height near the lower edge of frame; the other arm stays relaxed and mostly out of frame. The can remains generally stable, with only tiny grip micro-adjustments.

PRODUCT HANDLING: Relaxed one-hand grip; product stays below chin level at all times; never approaches mouth/face; no sipping or drinking gestures; no pointing directly at the can—just natural holding during the “trail break” moment.

PRODUCT VISIBILITY: Only a partial section of the can appears in frame (cropped/obscured by fingers and framing). Fine printed text, nutrition labels, and barcodes are not fully visible; any logo presence is partial and not fully readable.

MOTION STYLE: Minimal natural movement only—subtle handheld camera drift, slight posture shift, tiny hand micro-adjustments; no fast motion. Lip motion remains continuous with no pauses or resets.

LIGHTING: Match the reference image lighting exactly (natural, realistic; no stylized changes).

ENVIRONMENT: Exactly the same background/location as the reference image; no added props or changes.       

ENDING FRAME: The creator remains in the same framing and posture as prior moments; motion gently settles while lip motion continues through the final frame, maintaining a stable, seamless end state.''',  # your script output here
        duration_seconds=8
    )

    print(result)
