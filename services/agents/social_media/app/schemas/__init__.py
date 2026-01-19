# schemas/__init__.py
from app.schemas.tiktok import (
    PostRequest,
    PostResponse,
    PostHistoryItem,
    PostHistoryResponse,
    TokenRequest,
    TokenResponse
)
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.oauth import OAuthCodeExchange, OAuthTokenResponse

__all__ = [
    "PostRequest",
    "PostResponse",
    "PostHistoryItem",
    "PostHistoryResponse",
    "TokenRequest",
    "TokenResponse",
    "ChatRequest",
    "ChatResponse",
    "OAuthCodeExchange",
    "OAuthTokenResponse"
]
