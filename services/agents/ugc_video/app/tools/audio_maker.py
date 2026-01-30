"""
UGC Audio Maker Tool for CrewAI
Generates realistic voice audio from dialogue text using ElevenLabs API directly
Uploads generated audio to S3
"""

import os
import requests
from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from app.core.config import get_settings
from app.services.s3_utils import upload_file_to_s3, get_s3_key_for_upload
from app.config.avatars import get_avatar_voice_id, get_avatar_voice_name


# Legacy voice map for backward compatibility
AVATAR_VOICE_MAP = {
    1: "Harry",
    2: "Rachel",
    3: "Drew",
    4: "Clyde",
    5: "Paul",
    6: "Aria",
    7: "Domi",
    8: "Dave",
    9: "Roger",
    10: "Fin"
}


class UGCAudioMakerInput(BaseModel):
    """Input schema for UGC Audio Maker Tool."""
    dialogue_text: str = Field(
        ...,
        description="The dialogue text to convert to speech (18-26 words for 8-second video)"
    )
    avatar_id: int = Field(
        default=1,
        description="Avatar ID that maps to a specific ElevenLabs voice (1=Harry, 2=Rachel, etc.)"
    )
    output_filename: str = Field(
        default="ugc_audio.mp3",
        description="Output filename for the generated audio (e.g., 'ugc_audio_1.mp3')"
    )
    conversation_id: str = Field(
        default="default",
        description="Conversation ID for S3 upload path organization"
    )


class UGCAudioMakerTool(BaseTool):
    name: str = "UGC Audio Generator"
    description: str = (
        "Converts UGC dialogue text into realistic voice audio using ElevenLabs API. "
        "Perfect for 8-second UGC videos with natural-sounding creator voiceovers. "
        "Uses avatar_id to automatically select the appropriate custom voice."
    )
    args_schema: Type[BaseModel] = UGCAudioMakerInput
    cache_function: bool = False
    
    def _run(
        self,
        dialogue_text: str,
        avatar_id: int = 1,
        output_filename: str = "ugc_audio.mp3",
        conversation_id: str = "default"
    ) -> str:
        """
        Generate audio from dialogue text using ElevenLabs API directly.
        Uploads the generated audio to S3.
        
        Args:
            dialogue_text: The dialogue to convert to speech
            avatar_id: Avatar ID that maps to a custom voice (1-9 for custom voices)
            output_filename: Name for the output audio file
            conversation_id: Conversation ID for S3 organization
            
        Returns:
            Success message with S3 URL or error message
        """
        # Get ElevenLabs API key from settings
        settings = get_settings()
        elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
        
        if not elevenlabs_api_key:
            return "Error: ELEVENLABS_API_KEY environment variable not set"
        
        # Get custom voice ID from avatar mapping
        custom_voice_id = get_avatar_voice_id(avatar_id)
        voice_name = get_avatar_voice_name(avatar_id)
        
        # Fallback to legacy voice map if custom voice not found
        if not custom_voice_id:
            voice_name = AVATAR_VOICE_MAP.get(avatar_id, "Harry")
            print(f"⚠️ Using legacy voice: {voice_name} (avatar_id: {avatar_id})")
            # For legacy voices, we'd need their voice IDs - for now return error
            return f"Error: No custom voice ID found for avatar {avatar_id}. Please use avatars 1-9."
        else:
            print(f"✅ Using custom voice: {voice_name} (ID: {custom_voice_id})")
        
        try:
            # ElevenLabs API endpoint for text-to-speech
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{custom_voice_id}"
            
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": elevenlabs_api_key
            }
            
            payload = {
                "text": dialogue_text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": 0.0,
                    "use_speaker_boost": True
                }
            }
            
            print(f"🎙️ Generating audio with ElevenLabs API...")
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code not in [200, 201]:
                return f"Error: ElevenLabs API returned status code {response.status_code}: {response.text}"
            
            # Save audio to file
            with open(output_filename, "wb") as f:
                f.write(response.content)
            
            # Verify file was created
            if not os.path.exists(output_filename):
                return f"Error: Audio file was not created: {output_filename}"
            
            file_size = os.path.getsize(output_filename)
            if file_size == 0:
                return f"Error: Audio file is empty: {output_filename}"
            
            print(f"✅ Audio generated: {file_size} bytes")
            
            # Upload to S3
            try:
                s3_key = get_s3_key_for_upload(conversation_id, output_filename, "audio")
                s3_url = upload_file_to_s3(output_filename, s3_key, content_type="audio/mpeg")
                
                # Clean up local file after successful upload
                os.remove(output_filename)
                
                return f"[AUDIO_GENERATION_COMPLETE] Audio successfully generated and uploaded to S3: {s3_url} (Custom Voice: {voice_name}, Avatar ID: {avatar_id}, Size: {file_size} bytes)"
            except Exception as s3_error:
                # If S3 upload fails, still return local file path
                return f"[AUDIO_GENERATION_COMPLETE] Audio generated locally (S3 upload failed): {output_filename} (Custom Voice: {voice_name}, Avatar ID: {avatar_id}, Size: {file_size} bytes). S3 Error: {str(s3_error)}"
            
        except Exception as e:
            return f"Error generating audio: {str(e)}"
