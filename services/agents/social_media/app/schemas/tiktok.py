"""
Pydantic schemas for request/response validation
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TokenRequest(BaseModel):
    """Request schema for adding TikTok token"""
    user_id: int = Field(..., description="User ID from your system")
    access_token: str = Field(..., description="TikTok access token")


class TokenResponse(BaseModel):
    """Response after adding token"""
    status: str
    message: str


class PostRequest(BaseModel):
    """Request schema for posting to TikTok"""
    user_id: int = Field(..., description="User ID from your system")
    video_url: str = Field(..., description="Publicly accessible video URL")
    caption: str = Field(..., max_length=150, description="Video caption (max 150 chars)")
    hashtags: list[str] = Field(default_factory=list, description="List of hashtags without #")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 1,
                "video_url": "https://example.com/video.mp4",
                "caption": "Check out this amazing video! 🔥",
                "hashtags": ["viral", "trending", "awesome"]
            }
        }


class PostResponse(BaseModel):
    """Response after posting to TikTok"""
    status: Literal["success", "error"]
    message: str
    post_id: int
    publish_id: str
    posted_at: datetime


class PostHistoryItem(BaseModel):
    """Single post in history"""
    post_id: int
    platform: str
    video_url: str
    caption: str | None
    hashtags: list[str]
    status: str
    publish_id: str | None
    created_at: datetime


class PostHistoryResponse(BaseModel):
    """Response for user's posting history"""
    posts: list[PostHistoryItem]
    count: int
