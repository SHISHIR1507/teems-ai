"""
Pydantic schemas for chat endpoints.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    """Response schema from chat endpoint"""
    message: str = Field(..., description="AI assistant's response")
    conversation_id: str = Field(..., description="Conversation ID")
    session_id: str = Field(..., description="Session ID")
    recommendations: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="List of recommended actions and agents"
    )
    tools_used: Optional[List[str]] = Field(
        None,
        description="List of tools used in this turn"
    )


class ActionClickedRequest(BaseModel):
    action_id: str
    session_id: str = "default"


class ResetRequest(BaseModel):
    session_id: str = "default"
