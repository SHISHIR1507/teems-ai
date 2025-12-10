from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field, conlist


class ChunkUpsert(BaseModel):
    id: str
    tenant_id: str
    document_id: str
    chunk_index: Optional[str] = None
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: conlist(float, min_length=1)


class UpsertRequest(BaseModel):
    chunks: List[ChunkUpsert]


class QueryRequest(BaseModel):
    tenant_id: str
    embedding: conlist(float, min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)


class ChunkHit(BaseModel):
    id: str
    document_id: str
    content: str
    metadata: dict[str, Any] | None
    score: float


class QueryResponse(BaseModel):
    hits: list[ChunkHit]


