"""
Request schemas for Notetaker API
"""
from pydantic import BaseModel, Field
from typing import Optional


class ScheduleMeetingRequest(BaseModel):
    """Request schema for scheduling a meeting"""
    meeting_link: str = Field(..., description="Meeting URL (Zoom, Teams, etc.)")
    start_time: str = Field(..., description="ISO format datetime string (e.g., '2024-01-15T14:30:00Z')")
    title: str = Field(..., description="Meeting title/name")
    
    class Config:
        json_schema_extra = {
            "example": {
                "meeting_link": "https://zoom.us/j/123456789",
                "start_time": "2024-12-25T14:30:00Z",
                "title": "Team Standup"
            }
        }


class ChatRequest(BaseModel):
    """Request schema for chat endpoint"""
    query: str = Field(..., description="User's question about the meeting")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "What were the main action items?"
            }
        }


class CallListRequest(BaseModel):
    """Request schema for listing calls (query params)"""
    limit: int = Field(default=50, ge=1, le=100, description="Number of results per page")
    offset: int = Field(default=0, ge=0, description="Pagination offset")
    status: Optional[str] = Field(None, description="Filter by status (scheduled, processing, completed, failed)")
