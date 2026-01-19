"""
OAuth schemas for TikTok authentication
"""

from pydantic import BaseModel
from typing import Optional


class OAuthCodeExchange(BaseModel):
    """Request schema for exchanging OAuth code for tokens"""
    code: str
    

class OAuthTokenResponse(BaseModel):
    """Response after successful token exchange"""
    success: bool
    user_id: int
    message: str
    tiktok_username: Optional[str] = None
