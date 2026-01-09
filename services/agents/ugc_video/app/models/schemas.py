"""
Pydantic models for request/response schemas
"""
from pydantic import BaseModel
from typing import Optional, List, Dict


class BrandSyncRequest(BaseModel):
    industry: str
    audience: str
    vibe: str
    conversation_id: Optional[str] = None


class BrandSyncResponse(BaseModel):
    conversation_id: str
    kai_response: str
    brand_locked: bool
    timestamp: str
    trace_url: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: str
    assistant_message: str
    steps: List[Dict]
    generated_images: Optional[List[str]] = None
    timestamp: str
    trace_url: Optional[str] = None


class ScriptRequest(BaseModel):
    ugc_image_path: str
    product_name: str
    avatar_id: int = 1
    tone: Optional[str] = "energetic and authentic"
    platform: Optional[str] = "Instagram"
    conversation_id: Optional[str] = None


class ScriptVideoResponse(BaseModel):
    conversation_id: str
    script: str
    dialogue: Optional[str] = None
    audio_url: Optional[str] = None
    video_url: Optional[str] = None
    ugc_image_path: str
    avatar_id: int
    voice_used: Optional[str] = None
    timestamp: str
    trace_url: Optional[str] = None
