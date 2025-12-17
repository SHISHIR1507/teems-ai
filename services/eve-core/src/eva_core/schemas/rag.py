from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class DocumentIngestRequest(BaseModel):
    tenant_id: str = Field(..., description="Tenant or workspace identifier")
    text: str = Field(..., description="Raw text to ingest")
    title: str | None = Field(default=None, description="Optional document title")
    metadata: dict[str, Any] = Field(default_factory=dict)


class FileIngestResponse(BaseModel):
    document_id: str
    chunks_created: int


class DocumentIngestResponse(BaseModel):
    document_id: str
    chunks_created: int


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    tenant_id: str
    query: str
    chat_history: list[ChatMessage] = Field(default_factory=list)
    llm_provider: Literal["openai", "gemini"] | None = None
    llm_model: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    conversation_id: str | None = Field(default=None, description="Conversation id for WS streaming")


class SourceChunk(BaseModel):
    chunk_id: str
    document_id: str
    title: str | None = None
    content: str
    score: float
    metadata: dict[str, Any] | None = None

class RecommendationItem(BaseModel):
    """Schema for a single recommended action"""
    action: str = Field(..., description="The recommended action text")
    score: float = Field(..., description="Similarity score (0.0-1.0)")
    id: int = Field(..., description="Action item ID")

class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    provider: str
    model: str
    latency_ms: int | None = None
    generated_at: datetime
    conversation_id: str = Field(..., description="Current conversation identifier")
    needs_internet: bool = Field(default=False, description="Whether answering requires internet research")

    recommendations: list[RecommendationItem] = Field(  
        default_factory=list,
        description="Recommended next actions based on user query"
    )


