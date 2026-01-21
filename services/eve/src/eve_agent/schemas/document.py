"""
Pydantic schemas for document endpoints.
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DocumentResponse(BaseModel):
    id: str
    filename: Optional[str]
    status: Optional[str]
    s3_url: Optional[str]
    created_at: datetime
    total_chunks: Optional[int]
    
    class Config:
        from_attributes = True


class DocumentUploadResponse(BaseModel):
    message: str
    document_id: str
    s3_url: str
