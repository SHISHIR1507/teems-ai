"""
Pydantic schemas for chat endpoints
"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request schema for chat endpoint"""
    user_id: int = Field(..., description="User ID")
    message: str = Field(..., description="User's message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 1,
                "message": "Post this video https://example.com/video.mp4 with caption 'Hello world!'"
            }
        }


class ChatResponse(BaseModel):
    """Response schema from chat endpoint"""
    message: str = Field(..., description="AI assistant's response")
    action_taken: str | None = Field(default=None, description="Action performed (e.g., 'posted')")
    post_id: int | None = Field(default=None, description="Post ID if video was posted")
    publish_id: str | None = Field(default=None, description="TikTok publish ID if posted")
