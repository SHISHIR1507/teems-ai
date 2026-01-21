"""
Pydantic schemas for chat endpoints.
"""
from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ActionClickedRequest(BaseModel):
    action_id: str
    session_id: str = "default"


class ResetRequest(BaseModel):
    session_id: str = "default"
