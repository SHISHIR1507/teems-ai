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
    product_name: str = Field(..., description="Product name")
    conversation_id: Optional[str] = Field(None, description="Optional conversation ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "industry": "skincare",
                "audience": "Gen Z women",
                "vibe": "authentic and relatable",
                "product_name": "Glow Serum",
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


class ConversationState(BaseModel):
    """Conversation state tracking"""
    brand_locked: bool = Field(False, description="Whether brand context is synced")
    brand_industry: Optional[str] = Field(None, description="Brand industry")
    brand_audience: Optional[str] = Field(None, description="Target audience")
    brand_vibe: Optional[str] = Field(None, description="Brand vibe")
    product_name: Optional[str] = Field(None, description="Product name")
    person_url: Optional[str] = Field(None, description="Person/creator image URL")
    avatar_id: Optional[int] = Field(None, description="Avatar ID if using predefined avatar")
    product_url: Optional[str] = Field(None, description="Product image URL")
    generated_images: List[str] = Field(default_factory=list, description="Generated UGC image URLs")
    has_person: bool = Field(False, description="Whether person image is uploaded")
    has_product: bool = Field(False, description="Whether product image is uploaded")
    has_product_name: bool = Field(False, description="Whether product name is provided")
    has_generated_images: bool = Field(False, description="Whether UGC images are generated")
    next_step: Optional[str] = Field(None, description="Suggested next step for user")


class ChatResponse(BaseModel):
    """Response schema for UGC chat/upload"""
    conversation_id: str = Field(..., description="Conversation ID")
    assistant_message: str = Field(..., description="Assistant's response message")
    steps: List[Dict] = Field(..., description="Processing steps")
    generated_images: Optional[List[str]] = Field(None, description="Generated image URLs")
    conversation_state: Optional[ConversationState] = Field(None, description="Current conversation state")
    show_regenerate_button: bool = Field(False, description="Whether to show regenerate button in UI")
    timestamp: str = Field(..., description="ISO timestamp")
    trace_url: Optional[str] = Field(None, description="LangSmith trace URL")


class ScriptRequest(BaseModel):
    """Request schema for script generation"""
    ugc_image_path: str = Field(..., description="S3 URL or path to UGC image")
    conversation_id: str = Field(..., description="Conversation ID (required to retrieve brand context)")
    product_name: Optional[str] = Field(None, description="Product name (retrieved from conversation if not provided)")
    avatar_id: Optional[int] = Field(None, description="Avatar ID for voice selection (retrieved from conversation if not provided)")
    tone: Optional[str] = Field("energetic and authentic", description="Script tone")
    platform: Optional[str] = Field("Instagram", description="Target platform")
    
    class Config:
        json_schema_extra = {
            "example": {
                "ugc_image_path": "https://s3.../generated_image_1.png",
                "conversation_id": "uuid-here",
                "product_name": "Glow Serum (optional - retrieved from conversation)",
                "avatar_id": 1,
                "tone": "energetic and authentic",
                "platform": "Instagram"
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
