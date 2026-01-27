"""
Pydantic models for request/response schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ChatRequest(BaseModel):
    """Request schema for chat endpoint"""
    message: str = Field(..., description="User's message")
    conversation_id: Optional[str] = Field(None, description="Conversation ID (optional)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Create a 10-slide presentation about quantum computing",
                "conversation_id": "optional-uuid"
            }
        }


class ChatResponse(BaseModel):
    """Response schema from chat endpoint"""
    message: str = Field(..., description="AI assistant's response")
    action_taken: Optional[str] = Field(None, description="Action performed")
    task_id: Optional[str] = Field(None, description="Task ID for async operations")
    presentation_id: Optional[str] = Field(None, description="Presentation ID if created")
    download_url: Optional[str] = Field(None, description="Download URL if available")
    conversation_id: Optional[str] = Field(None, description="Conversation ID")
    status_url: Optional[str] = Field(None, description="URL to check task status")


class PresentationResponse(BaseModel):
    """Presentation response schema"""
    id: str
    conversation_id: str
    tenant_id: str
    title: Optional[str] = None
    status: str
    s3_url: Optional[str] = None
    slidespeak_presentation_id: Optional[str] = None
    created_at: str
    updated_at: str
    is_downloadable: bool = Field(default=False, description="Whether presentation is ready for download")
    file_size: Optional[int] = Field(None, description="File size in bytes if available")
    file_format: Optional[str] = Field(None, description="File format (e.g., 'pptx', 'pdf')")


class PresentationListResponse(BaseModel):
    """List of presentations"""
    presentations: List[PresentationResponse]
    total: int
    limit: int
    offset: int


class UploadRequest(BaseModel):
    """Request schema for file upload"""
    conversation_id: Optional[str] = Field(None, description="Conversation ID")


class UploadResponse(BaseModel):
    """Response schema for file upload"""
    document_id: str
    filename: str
    s3_url: str
    processing_status: str
    message: str


class BrandSyncRequest(BaseModel):
    """Request schema for brand sync"""
    conversation_id: str
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    font: Optional[str] = None


class BrandSyncResponse(BaseModel):
    """Response schema for brand sync"""
    conversation_id: str
    message: str
    brand_locked: bool
    timestamp: str


class TaskStatusResponse(BaseModel):
    """Response schema for task status"""
    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str


class WebhookPayload(BaseModel):
    """Webhook payload from SlideSpeak"""
    event_type: Optional[str] = None
    task_id: Optional[str] = None
    status: Optional[str] = None
    presentation_id: Optional[str] = None
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
