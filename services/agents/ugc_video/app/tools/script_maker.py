"""
UGC Script Maker Tool for CrewAI
Generates UGC dialogue and Veo-3-compatible 8-second video scripts using GPT-5.2 with vision
"""

import os
import base64
import uuid
from typing import Type, Optional
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from openai import OpenAI
from app.core.config import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL
from app.services.s3_utils import upload_file_to_s3, get_s3_key_for_upload


class UGCScriptMakerInput(BaseModel):
    """Input schema for UGC Script Maker Tool."""
    ugc_image_reference: str = Field(
        ...,
        description="Path or URL to the UGC image reference"
    )
    product_name: str = Field(
        ...,
        description="Name of the product to feature in the video"
    )
    tone: str = Field(
        ...,
        description="Desired tone for the video (e.g., energetic, calm, professional, playful)"
    )
    platform: str = Field(
        ...,
        description="Target platform for the video (e.g., TikTok, Instagram, YouTube Shorts)"
    )
    # Brand context (required)
    industry: str = Field(..., description="Brand industry context")
    audience: str = Field(..., description="Brand audience context")
    vibe: str = Field(..., description="Brand vibe context")
    conversation_id: str = Field(
        default="default",
        description="Conversation ID for S3 organization"
    )
    output_filename: str = Field(
        default=None,
        description="Optional filename to save the script (default: auto-generated)"
    )


class UGCScriptMakerTool(BaseTool):
    name: str = "UGC Script Maker"
    description: str = (
        "Analyzes a UGC image to generate authentic 8-second dialogue, then creates a "
        "Veo-3-compatible silent video script. Saves the output to a text file and returns the filename."
    )
    args_schema: Type[BaseModel] = UGCScriptMakerInput
    cache_function: bool = False
    
    def _encode_image(self, image_path: str) -> str:
        """Encode image to base64 for vision API."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def _generate_dialogue(
        self, 
        client: OpenAI, 
        image_path: str, 
        product_name: str, 
        tone: str, 
        platform: str,
        industry: str,
        audience: str,
        vibe: str
    ) -> str:
        """Generate 8-second UGC dialogue using GPT-5.2 vision."""
        
        dialogue_prompt = f"""You are generating dialogue for an UGC video.

Brand context (LOCKED):
Industry: {industry}
Audience: {audience}
Vibe: {vibe}

This context must subtly influence the dialogue through:
- Word choice and phrasing that resonates with the audience
- Energy level and pacing that matches the vibe
- Relatability to the industry space

Do NOT:
- Repeat the brand context verbatim
- Use marketing slogans or ad language
- Add calls-to-action

Dialogue requirements:
- Target 18–26 words (slightly longer than typical ads)
- The dialogue should be around the image and the product 
- Use natural spoken pacing with short pauses implied by commas or em dashes
- Dialogue should feel like one continuous thought, not punchy slogans
- Allow reflective, moment-to-moment narration (e.g., effort, progress, mindset)
- First-person only ("I", "my")
- Calm, grounded delivery — not rushed
- No call-to-action
- No exaggerated excitement
- Must be safe for continuous lip motion (no abrupt stops)

Style guidance:
- Think "talking while doing something" rather than "selling"
- Avoid sharp sentence breaks; prefer flowing phrases
- One idea evolving into the next
- Let the brand context influence the creator's voice naturally

Output ONLY the dialogue text.
No quotes. No labels.
"""

        # Check if image is URL or local path
        if image_path.startswith(('http://', 'https://')):
            image_content = {"type": "image_url", "image_url": {"url": image_path}}
        else:
            base64_image = self._encode_image(image_path)
            image_content = {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{base64_image}"}
            }
        
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": dialogue_prompt},
                            image_content
                        ]
                    }
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Error generating dialogue: {str(e)}"
    
    def _run(
        self,
        ugc_image_reference: str,
        product_name: str,
        tone: str,
        platform: str,
        industry: str,
        audience: str,
        vibe: str,
        conversation_id: str = "default",
        output_filename: str = None
    ) -> str:
        """
        Generate dialogue and 8-second video script optimized for Veo 3.
        Saves output to a text file and uploads to S3.
        
        Args:
            ugc_image_reference: Path or URL to the UGC image
            product_name: Name of the product
            tone: Desired tone for the video
            platform: Target platform
            industry: Brand industry context
            audience: Brand audience context
            vibe: Brand vibe context
            conversation_id: Conversation ID for S3 organization
            output_filename: Optional filename to save the script (default: auto-generated)
            
        Returns:
            S3 URL of the saved script file
        """
        # Initialize OpenAI client
        if not OPENAI_API_KEY:
            return "Error: OPENAI_API_KEY environment variable not set"
        
        client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL
        )
        
        # Stage 1: Generate dialogue using vision
        dialogue = self._generate_dialogue(
            client, 
            ugc_image_reference, 
            product_name, 
            tone, 
            platform,
            industry,
            audience,
            vibe
        )
        
        if dialogue.startswith("Error"):
            return dialogue
        
        # Stage 2: Generate video script with dialogue context
        system_prompt = f"""You are a professional UGC video director and lip-sync supervisor for short-form AI-generated videos.

BRAND CONTEXT (LOCKED):
Industry: {industry}
Audience: {audience}
Vibe: {vibe}

This context must subtly influence the video script through:
- Visual energy and body language that matches the vibe
- Framing and environment that feels authentic to the industry
- Overall creator presence that resonates with the audience

Do NOT:
- Repeat the brand context verbatim
- Add marketing elements or text overlays
- Force unnatural product placement

DIALOGUE CONTEXT:
The creator will be speaking the provided dialogue using visual-only lip motion (NO AUDIO).

CORE OBJECTIVE:
Generate a SINGLE, continuous-shot, production-ready 8-second UGC video script that is perfectly stable for lip-sync and identity consistency.

ABSOLUTE STRUCTURE CONSTRAINT (MANDATORY — NO EXCEPTIONS):
- The video MUST be ONE continuous shot from start to end
- NO scene changes, NO cuts, NO transitions, NO jump cuts
- Do NOT describe multiple scenes, moments, or locations
- Do NOT use words such as: "Scene 1", "Scene 2", "cut", "montage", "jump", "hero shot", "end card"
- The camera framing MUST remain consistent for the full duration

GLOBAL RULES (CRITICAL):
- Assume the person, face, body, clothing, hair, and environment come directly from the provided UGC image reference
- Do NOT invent new outfits, props, locations, text, graphics, music, or sound effects
- The video is ALWAYS silent (no speech audio, no music, no ambient sound)
- Do NOT include on-screen text, subtitles, captions, or stickers
- Everything described must be physically filmable and realistic

LIP MOTION CONSTRAINT (MANDATORY):
- continuous speech-mimicking lip motion MUST persist from 0 seconds through the final frame
- Lip motion must NOT pause, stop, freeze, or reset at any time
- Lip motion continues even if all other motion becomes minimal near the end

PRODUCT HANDLING RULES (MANDATORY):
- The product must NEVER approach the mouth or face
- NO sipping, NO pretending to drink
- Product stays below chin level at all times (chest or torso height only)
- Grip must look relaxed and natural
- Product position remains generally stable throughout the clip

PRODUCT VISIBILITY & BRAND SAFETY:
- The product must NEVER be fully visible
- Only a partial section of the product may appear in frame
- Fingers, framing, or crop must naturally obscure fine printed text, nutrition labels, and barcodes
- Logo may be partially visible but not fully readable

CAMERA & MOTION STYLE:
- Medium close-up framing (chest to face)
- Subtle handheld realism only
- NO zooms, NO punch-ins, NO pans, NO fast movement
- Allowed motion is limited to:
  • natural head micro-movement
  • subtle hand micro-adjustments
  • minor posture shifts

EXPRESSION & PERFORMANCE:
- Natural, confident creator demeanor
- Calm, conversational facial expression
- NO exaggerated acting, laughter, or dramatic reactions
- Eye contact with the camera should feel intentional and steady

ENDING FRAME (IMPORTANT):
- The final frame must visually match the previous frames
- Motion may gently settle, but lip motion MUST continue
- The ending frame should be stable enough to chain into the next clip seamlessly

OUTPUT FORMAT (STRICT — FOLLOW EXACTLY):

FORMAT:
DURATION:
OUTPUT CONSTRAINT:
CAMERA:
SUBJECT:
ACTION TIMELINE:
  0–8s:
PRODUCT HANDLING:
PRODUCT VISIBILITY:
MOTION STYLE:
LIGHTING:
ENVIRONMENT:
ENDING FRAME:

IMPORTANT:
If the script would require more than one scene, camera change, cut, subtitle, or sip — DO NOT GENERATE IT.
"""
        
        # User prompt with context
        user_prompt = f"""Generate an 8-second video script with the following parameters:

Brand context (LOCKED):
- Industry: {industry}
- Audience: {audience}
- Vibe: {vibe}

UGC Image Reference: {ugc_image_reference}
Product Name: {product_name}
Tone: {tone}
Platform: {platform}
Dialogue (lip motion): {dialogue}

Use the visual identity from the UGC image reference. Create a script that showcases the product naturally and authentically while the creator speaks the dialogue. Let the brand context influence the visual energy and creator presence."""
        
        try:
            # Call GPT-4o
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.4
            )
            
            script = response.choices[0].message.content
            
            # Format output with both dialogue and script
            output = f"""=== UGC DIALOGUE ===
{dialogue}

=== VIDEO SCRIPT ===
{script}"""
            
            # Generate filename if not provided
            if not output_filename:
                output_filename = f"script_{uuid.uuid4().hex[:8]}.txt"
            
            # Save to local file temporarily
            with open(output_filename, 'w', encoding='utf-8') as f:
                f.write(output)
            
            # Upload to S3
            try:
                s3_key = get_s3_key_for_upload(conversation_id, output_filename, "script")
                s3_url = upload_file_to_s3(output_filename, s3_key, content_type="text/plain")
                
                # Clean up local file after successful upload
                os.remove(output_filename)
                
                return f"[SCRIPT_SAVED] Script uploaded to S3: {s3_url}\n\n{output}"
            except Exception as s3_error:
                # If S3 upload fails, still return local file path
                return f"[SCRIPT_SAVED] Script saved locally (S3 upload failed): {output_filename}\n\n{output}"
            
        except Exception as e:
            return f"Error generating script: {str(e)}"
