"""
Response schemas for Notetaker API
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class CallResponse(BaseModel):
    """Call/meeting response schema"""
    id: str
    tenant_id: str
    user_id: Optional[str] = None
    meeting_id: Optional[str] = None
    title: str
    meeting_link: str
    start_time: str
    transcript: Optional[str] = None
    summary: Optional[str] = None
    action_items: Optional[Dict[str, Any]] = None
    status: str
    created_at: str
    updated_at: str
    has_transcript: bool = Field(default=False, description="Whether transcript is available")
    has_summary: bool = Field(default=False, description="Whether summary is available")
    has_action_items: bool = Field(default=False, description="Whether action items are available")


class ChatSource(BaseModel):
    """Lightweight source information for chat responses"""
    call_id: str = Field(..., description="Call ID used as a source")
    meeting_title: str = Field(..., description="Title of the meeting used as a source")
    snippet_preview: Optional[str] = Field(
        default=None,
        description="Optional short preview of the context used from this meeting",
    )


class ScheduleMeetingResponse(BaseModel):
    """Response schema for meeting scheduling"""
    success: bool
    message: str
    call_id: str
    call: CallResponse
    nylas_meeting_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Response schema for chat endpoint"""
    answer: str = Field(..., description="AI-generated answer")
    meeting_title: str
    chunks_used: int = Field(..., description="Number of context chunks used")
    query: str
    sources: Optional[List[ChatSource]] = Field(
        default=None,
        description="Optional list of meetings that were used as sources for this answer",
    )
    deprecated_endpoint: bool = Field(
        default=False,
        description="True if this response came from a deprecated endpoint",
    )


class CallListResponse(BaseModel):
    """Response schema for call list"""
    calls: List[CallResponse]
    total: int
    limit: int
    offset: int


class WebhookResponse(BaseModel):
    """Response schema for webhook endpoints"""
    status: str = "OK"
    message: Optional[str] = None
