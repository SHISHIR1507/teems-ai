"""
UGC Script Maker Tool for CrewAI
Generates Veo-3-compatible 8-second video scripts using GPT-5.2
Supports Physical Product, Digital Product, and Service types
"""
from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from openai import OpenAI
import langsmith
from langsmith import traceable

from ..config import get_settings
from ..models.conversation import UGCType


class UGCScriptMakerInput(BaseModel):
    """Input schema for UGC Script Maker Tool."""
    ugc_image_reference: str = Field(
        ...,
        description="Path or URL to the UGC image reference"
    )
    product_name: str = Field(
        ...,
        description="Name of the product or service to feature in the video"
    )
    tone: str = Field(
        ...,
        description="Desired tone for the video (e.g., energetic, calm, professional, playful)"
    )
    platform: str = Field(
        ...,
        description="Target platform for the video (e.g., TikTok, Instagram, YouTube Shorts)"
    )
    ugc_type: str = Field(
        default="physical_product",
        description="Type of UGC: physical_product, digital_product, or service"
    )


class UGCScriptMakerTool(BaseTool):
    name: str = "UGC Script Maker"
    description: str = (
        "Generates a highly detailed, Veo-3-compatible 8-second video script "
        "based on a selected UGC image. Supports physical products, digital products, and services."
    )
    args_schema: Type[BaseModel] = UGCScriptMakerInput
    cache_function: bool = False
    
    def _run(
        self,
        ugc_image_reference: str,
        product_name: str,
        tone: str,
        platform: str,
        ugc_type: str = "physical_product"
    ) -> str:
        """
        Generate an 8-second video script optimized for Veo 3.
        
        Args:
            ugc_image_reference: Path or URL to the UGC image
            product_name: Name of the product or service
            tone: Desired tone for the video
            platform: Target platform
            ugc_type: Type of UGC content
            
        Returns:
            Structured 8-second video script
        """
        settings = get_settings()
        
        if not settings.aiml_api_key:
            return "Error: AIML_API_KEY environment variable not set"
        
        client = OpenAI(
            api_key=settings.aiml_api_key,
            base_url=settings.aiml_base_url
        )
        
        # Base system prompt (same for all types)
        base_system_prompt = '''You are a professional UGC commercial video director and script supervisor.

Your task:
- Generate a SINGLE, production-ready video script optimized for Veo 3
- The script must feel like authentic creator-made UGC, not a polished advertisement
- The script must strictly follow the output format below
- Output ONLY the script, no explanations, no markdown

GLOBAL RULES (CRITICAL):
- Assume the person, face, clothing, hair, and environment come directly from the provided UGC image reference
- Do NOT invent new identities, outfits, locations, props, or backgrounds
- The video is ALWAYS silent (no speech audio, no music, no ambient sound, no captions)
- Lip motion may be present but is visual-only
- Everything described must be physically filmable

PLATFORM & FORMAT RULES:
- Default format: Vertical 9:16 (Instagram Stories / Reels)
- Respect Instagram safe areas (avoid extreme top and bottom edges)
- Duration must match the requested duration exactly

LIP MOTION CONSTRAINT (MANDATORY):
- Subtle, continuous speech-mimicking lip motion must persist from 0 seconds through the final frame
- Lip motion must NOT stop, pause, or freeze at any point, including the ending frame
- Lip motion continues even if body, camera, or product motion settles

CAMERA & MOTION STYLE:
- Medium close-up unless specified otherwise
- Subtle handheld realism
- Gentle push-in or static framing only
- No fast pans, no aggressive movement

CLIP CHAINING RULES (IMPORTANT):
- The ending frame may become more stable to allow seamless continuation into the next clip
- Lip motion must still continue through the final frame

EXPRESSION & PERFORMANCE:
- Energetic but natural creator demeanor
- No exaggerated facial expressions
- No wide smiles, laughter, or comedic acting
- Eye contact with the camera should feel confident and intentional

OUTPUT FORMAT (STRICT — FOLLOW EXACTLY):

FORMAT:
DURATION:
OUTPUT CONSTRAINT:
SCENE:
CAMERA:
SUBJECT:
ACTION TIMELINE:
  0–2s:
  2–4s:
  4–6s:
  6–8s:
DEPTH OF FIELD:
SUBTLE MOTION:
ENVIRONMENT:
LIGHTING:
MOTION DETAILS:
ENDING FRAME:

'''
        
        # Type-specific additions
        type_specific_rules = ""
        if ugc_type == UGCType.PHYSICAL_PRODUCT.value:
            type_specific_rules = '''
PRODUCT VISIBILITY & TEXT SAFETY (MANDATORY):
- The product must NEVER be fully visible
- Only a partial section of the product may appear in frame at any time
- Fingers, framing, angle, and/or crop must naturally obscure fine printed text, nutrition labels, and barcodes
- Only brand colors and a partial logo may be visible
- Never request readable fine print

PRODUCT HANDLING RULES:
- Product stays at chest or torso level
- Grip must look relaxed and natural
- Product handling must feel casual, not deliberately showcased
- The product must NEVER approach the mouth or face
- No sipping, no pretending to drink
'''
        elif ugc_type == UGCType.DIGITAL_PRODUCT.value:
            type_specific_rules = '''
DEVICE & SCREEN VISIBILITY (MANDATORY):
- The device (laptop, tablet, or phone) should be naturally held or positioned
- The screen should show the digital product interface clearly but not overwhelm the person
- Device should feel integrated into the scene, not staged
- Person should interact naturally with the device

DEVICE HANDLING RULES:
- Device stays at comfortable viewing level (chest to eye level)
- Person can point to or gesture toward the screen naturally
- Device should feel like a natural part of the creator's environment
'''
        elif ugc_type == UGCType.SERVICE.value:
            type_specific_rules = '''
SERVICE PRESENTATION (MANDATORY):
- Focus on the person talking about or presenting the service
- If a logo is present, it should be naturally integrated (background, device screen, or subtle watermark)
- Person should gesture naturally while explaining
- Service should be conveyed through person's expression and body language

LOGO PLACEMENT RULES:
- Logo should be subtle and not distract from the person
- Can appear on a device screen, background element, or as a watermark
- Never make the logo the main focus
'''
        
        system_prompt = base_system_prompt + type_specific_rules
        
        # User prompt with context
        user_prompt = f"""Generate an 8-second video script with the following parameters:

UGC Image Reference: {ugc_image_reference}
Product/Service Name: {product_name}
Tone: {tone}
Platform: {platform}
UGC Type: {ugc_type}

Use the visual identity from the UGC image reference. Create a script that showcases the {'product' if ugc_type != UGCType.SERVICE.value else 'service'} naturally and authentically."""
        
        try:
            # Call GPT-5.2 via AI/ML API
            response = client.chat.completions.create(
                model="openai/gpt-5-2",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.4
            )
            
            script = response.choices[0].message.content
            return script
            
        except Exception as e:
            return f"Error generating script: {str(e)}"

