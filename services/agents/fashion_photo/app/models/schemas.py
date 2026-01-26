"""
Pydantic models for request/response schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# Session Schemas
class SessionRequest(BaseModel):
    """Request schema for creating a session"""
    conversation_id: Optional[str] = Field(None, description="Optional conversation ID (UUID)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "conversation_id": None
            }
        }


class SessionResponse(BaseModel):
    """Response schema for session"""
    id: str
    tenant_id: str
    user_id: Optional[str] = None
    stage: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str


# Avatar Schemas
class AvatarRequest(BaseModel):
    """Request schema for avatar selection/upload"""
    session_id: str = Field(..., description="Session ID")
    avatar_url: Optional[str] = Field(None, description="Preset avatar URL")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "uuid-here",
                "avatar_url": "https://example.com/avatar.png"
            }
        }


class AvatarResponse(BaseModel):
    """Response schema for avatar"""
    id: str
    session_id: str
    s3_url: str
    avatar_type: str
    created_at: str


class AvatarListResponse(BaseModel):
    """List of avatars"""
    avatars: List[AvatarResponse]
    total: int


# Apparel Schemas
class ApparelRequest(BaseModel):
    """Request schema for apparel upload"""
    session_id: str = Field(..., description="Session ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "uuid-here"
            }
        }


class ApparelResponse(BaseModel):
    """Response schema for apparel"""
    id: str
    session_id: str
    s3_url: str
    filename: Optional[str] = None
    vision_analysis: Optional[str] = None
    created_at: str


class ApparelListResponse(BaseModel):
    """List of apparel"""
    apparel: List[ApparelResponse]
    total: int


# Scene Schemas
class SceneSuggestionRequest(BaseModel):
    """Request schema for scene suggestions"""
    session_id: str = Field(..., description="Session ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "uuid-here"
            }
        }


class SceneSuggestionResponse(BaseModel):
    """Response schema for scene suggestions"""
    scenes: List[str]
    message: str
    status: str


# Image Generation Schemas
class ImageGenerationRequest(BaseModel):
    """Request schema for image generation"""
    session_id: str = Field(..., description="Session ID")
    scene_description: str = Field(..., description="Scene description for generation")
    previous_image_urls: Optional[List[str]] = Field(None, description="Previous images for editing")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "uuid-here",
                "scene_description": "Urban street style with natural lighting",
                "previous_image_urls": None
            }
        }


class ImageGenerationResponse(BaseModel):
    """Response schema for image generation"""
    image_urls: List[str]
    message: str
    status: str
    task_id: Optional[str] = None
    batch_id: Optional[str] = None


class GeneratedImageResponse(BaseModel):
    """Response schema for a generated image"""
    id: str
    session_id: str
    s3_url: str
    angle: Optional[str] = None
    scene: Optional[str] = None
    created_at: str


class ImageListResponse(BaseModel):
    """List of generated images"""
    images: List[GeneratedImageResponse]
    total: int
    limit: int
    offset: int


# Chat Schemas
class ChatRequest(BaseModel):
    """Request schema for chat endpoint"""
    message: str = Field(default="", description="User's message (empty for welcome)")
    session_id: Optional[str] = Field(None, description="Session ID (optional, will create if not provided)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Suggest some scenes for my fashion photos",
                "session_id": "optional-uuid"
            }
        }


class ChatResponse(BaseModel):
    """Response schema from chat endpoint"""
    message: str = Field(..., description="AI assistant's response")
    action_taken: Optional[str] = Field(None, description="Action performed")
    session_id: str = Field(..., description="Session ID")
    stage: str = Field(..., description="Current workflow stage")
    image_urls: Optional[List[str]] = Field(None, description="Generated image URLs if any")
    batch_id: Optional[str] = Field(None, description="Generation batch ID when images were created")
    run_id: Optional[str] = Field(None, description="LangSmith run ID")


# Upload Schemas
class UploadRequest(BaseModel):
    """Request schema for file upload"""
    session_id: str = Field(..., description="Session ID")
    upload_type: str = Field(..., description="Type: 'avatar' or 'apparel'")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "uuid-here",
                "upload_type": "apparel"
            }
        }


class UploadResponse(BaseModel):
    """Response schema for file upload"""
    urls: List[str]
    session_id: str
    upload_type: str
    stage: str
    message: str


# Feedback Schemas
class FeedbackRequest(BaseModel):
    """Request schema for feedback"""
    session_id: str = Field(..., description="Session ID")
    image_url: str = Field(..., description="URL of the image being rated")
    score: int = Field(..., description="1 for Like, -1 for Dislike")
    run_id: Optional[str] = Field(None, description="LangSmith run ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "uuid-here",
                "image_url": "https://example.com/image.png",
                "score": 1,
                "run_id": None
            }
        }


class FeedbackResponse(BaseModel):
    """Response schema for feedback"""
    status: str
    message: str


# Health Schemas
class HealthResponse(BaseModel):
    """Response schema for health check"""
    status: str
    service: str
    version: str
