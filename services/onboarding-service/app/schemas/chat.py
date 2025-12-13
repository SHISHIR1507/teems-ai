from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role: user, assistant, or system")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message")
    conversation_id: str | None = Field(
        None, description="Conversation ID to resume existing conversation"
    )


class ChatResponse(BaseModel):
    message: str = Field(..., description="Assistant response message")
    conversation_id: str = Field(..., description="Conversation ID")
    current_stage: str = Field(..., description="Current onboarding stage")
    stage_completed: bool = Field(
        False, description="Whether the current stage was just completed"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

