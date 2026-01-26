"""
Pydantic models for request/response schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ChatRequest(BaseModel):
    """Request schema for chat endpoint"""
    message: str = Field(..., description="User's message")
    conversation_id: Optional[str] = Field(None, description="Conversation ID (optional)")
    asset_id: Optional[str] = Field(None, description="Asset ID if user just uploaded via /v1/upload")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Post this video https://example.com/video.mp4 to TikTok with caption 'Hello!'",
                "conversation_id": "optional-uuid"
            }
        }


class ChatResponse(BaseModel):
    """Response schema from chat endpoint"""
    message: str = Field(..., description="AI assistant's response")
    action_taken: Optional[str] = Field(None, description="Action performed")
    post_ids: Optional[List[str]] = Field(None, description="Post IDs if video(s) were posted")
    conversation_id: Optional[str] = Field(None, description="Conversation ID")


class TokenRequest(BaseModel):
    """Request schema for adding platform token"""
    access_token: str = Field(..., description="Platform access token")
    refresh_token: Optional[str] = Field(None, description="Refresh token (TikTok)")
    platform_user_id: Optional[str] = Field(None, description="Platform-specific user ID (e.g. TikTok open_id)")


class TokenResponse(BaseModel):
    """Response after adding token"""
    status: str
    message: str


class PostRequest(BaseModel):
    """Request schema for posting video"""
    video_url: str = Field(..., description="Publicly accessible video URL")
    caption: str = Field(..., max_length=150, description="Video caption (max 150 chars)")
    hashtags: List[str] = Field(default_factory=list, description="List of hashtags without # (TikTok)")
    page_id: Optional[str] = Field(None, description="Facebook Page ID (Facebook only)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "video_url": "https://example.com/video.mp4",
                "caption": "Check this out! 🔥",
                "hashtags": ["viral", "trending"]
            }
        }


class PostResponse(BaseModel):
    """Response after posting"""
    status: str
    message: str
    post_id: str
    publish_id: str
    platform: str
    posted_at: str


class PostHistoryItem(BaseModel):
    """Single post in history"""
    id: str
    platform: str
    video_url: str
    caption: Optional[str] = None
    hashtags: List[str]
    status: str
    publish_id: Optional[str] = None
    created_at: str


class PostHistoryResponse(BaseModel):
    """Response for posting history"""
    posts: List[PostHistoryItem]
    count: int
    limit: int
    offset: int


class ConversationResponse(BaseModel):
    """Conversation with messages"""
    id: str
    tenant_id: str
    created_at: str
    updated_at: str
    messages: List[Dict[str, Any]]


class ConversationListResponse(BaseModel):
    """List of conversations"""
    conversations: List[Dict[str, Any]]
    total: int
    limit: int
    offset: int


class TokenListResponse(BaseModel):
    """List of connected platforms"""
    platforms: List[str]
    count: int


class OAuthExchangeRequest(BaseModel):
    """OAuth code exchange request"""
    code: str = Field(..., description="Authorization code from platform")


class UploadResponse(BaseModel):
    """Response after uploading content (image/video)"""
    asset_id: str
    url: str
    display_url: str
    content_type: str
    type: str  # 'image' | 'video'
