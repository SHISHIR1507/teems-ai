"""
Pydantic models for request/response schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class BrandSyncRequest(BaseModel):
    """Request schema for brand sync"""
    industry: str = Field(..., description="Brand industry")
    audience: str = Field(..., description="Target audience")
    vibe: str = Field(..., description="Brand vibe/tone")
    conversation_id: Optional[str] = Field(None, description="Optional conversation ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "industry": "skincare",
                "audience": "Gen Z women",
                "vibe": "authentic and relatable",
                "conversation_id": "optional-uuid"
            }
        }


class BrandSyncResponse(BaseModel):
    """Response schema for brand sync"""
    conversation_id: str = Field(..., description="Conversation ID")
    kai_response: str = Field(..., description="Kai's brand reflection response")
    brand_locked: bool = Field(..., description="Whether brand is locked")
    timestamp: str = Field(..., description="ISO timestamp")
    trace_url: Optional[str] = Field(None, description="LangSmith trace URL")
    was_already_synced: bool = Field(default=False, description="Whether brand was already synced before this call")


class ChatResponse(BaseModel):
    """Response schema for UGC chat/upload"""
    conversation_id: str = Field(..., description="Conversation ID")
    assistant_message: str = Field(..., description="Assistant's response message")
    steps: List[Dict] = Field(..., description="Processing steps")
    generated_images: Optional[List[str]] = Field(None, description="Generated image URLs")
    timestamp: str = Field(..., description="ISO timestamp")
    trace_url: Optional[str] = Field(None, description="LangSmith trace URL")


class ScriptRequest(BaseModel):
    """Request schema for script generation"""
    ugc_image_path: str = Field(..., description="S3 URL or path to UGC image")
    product_name: str = Field(..., description="Product name")
    avatar_id: int = Field(1, description="Avatar ID for voice selection")
    tone: Optional[str] = Field("energetic and authentic", description="Script tone")
    platform: Optional[str] = Field("Instagram", description="Target platform")
    conversation_id: Optional[str] = Field(None, description="Conversation ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "ugc_image_path": "https://s3.../generated_image_1.png",
                "product_name": "Glow Serum",
                "avatar_id": 1,
                "tone": "energetic and authentic",
                "platform": "Instagram",
                "conversation_id": "optional-uuid"
            }
        }


class ScriptVideoResponse(BaseModel):
    """Response schema for script, audio, and video generation"""
    conversation_id: str = Field(..., description="Conversation ID")
    script: str = Field(..., description="Generated video script")
    dialogue: Optional[str] = Field(None, description="Dialogue text for audio")
    audio_url: Optional[str] = Field(None, description="S3 URL of generated audio")
    video_url: Optional[str] = Field(None, description="URL of generated video")
    ugc_image_path: str = Field(..., description="UGC image path used")
    avatar_id: int = Field(..., description="Avatar ID used")
    voice_used: Optional[str] = Field(None, description="Voice name used")
    timestamp: str = Field(..., description="ISO timestamp")
    trace_url: Optional[str] = Field(None, description="LangSmith trace URL")
    current_step: Optional[str] = Field(None, description="Current step: 'script', 'audio', 'video', 'completed'")
    total_steps: int = Field(default=3, description="Total number of steps")
    progress_percentage: Optional[int] = Field(None, description="Progress percentage (0-100)")


class ConversationResponse(BaseModel):
    """Response schema for conversation details"""
    conversation_id: str = Field(..., description="Conversation ID")
    tenant_id: str = Field(..., description="Tenant ID")
    user_id: Optional[str] = Field(None, description="User ID")
    brand: Optional[Dict[str, Any]] = Field(None, description="Brand context if locked")
    messages: List[Dict[str, Any]] = Field(..., description="Conversation messages")
    assets: List[Dict[str, Any]] = Field(..., description="Generated assets")
    created_at: str = Field(..., description="ISO timestamp")
    updated_at: str = Field(..., description="ISO timestamp")


class ConversationListResponse(BaseModel):
    """Response schema for conversation list"""
    conversations: List[ConversationResponse] = Field(..., description="List of conversations")
    total: int = Field(..., description="Total count")
    limit: int = Field(..., description="Limit used")
    offset: int = Field(..., description="Offset used")


class AssetResponse(BaseModel):
    """Response schema for asset details"""
    id: int = Field(..., description="Asset ID")
    conversation_id: str = Field(..., description="Conversation ID")
    asset_type: str = Field(..., description="Asset type")
    url: str = Field(..., description="Asset URL")
    filename: Optional[str] = Field(None, description="Filename")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Asset metadata")
    created_at: str = Field(..., description="ISO timestamp")


class AssetListResponse(BaseModel):
    """Response schema for asset list"""
    assets: List[AssetResponse] = Field(..., description="List of assets")
    total: int = Field(..., description="Total count")
    limit: int = Field(..., description="Limit used")
    offset: int = Field(..., description="Offset used")


class ErrorResponse(BaseModel):
    """Standardized error response"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Error detail")
    status_code: int = Field(..., description="HTTP status code")
