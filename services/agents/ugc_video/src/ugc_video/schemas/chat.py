from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
import uuid as uuid_pkg

from ..models.conversation import UGCType


class ChatRequest(BaseModel):
    message: str = Field(..., description="User's message")
    conversation_id: Optional[uuid_pkg.UUID] = Field(None, description="Existing conversation ID")


class ChatResponse(BaseModel):
    conversation_id: uuid_pkg.UUID
    assistant_message: str
    ugc_type: Optional[str] = None
    generated_images: Optional[List[str]] = None  # S3 URLs
    status: str
    timestamp: datetime


class GenerateVideoRequest(BaseModel):
    image_id: uuid_pkg.UUID = Field(..., description="ID of the selected image artifact")
    product_name: str = Field(..., description="Name of the product or service")
    tone: str = Field(default="energetic and authentic", description="Desired tone for the video")
    platform: str = Field(default="Instagram", description="Target platform")


class GenerateVideoResponse(BaseModel):
    conversation_id: uuid_pkg.UUID
    script: str
    video_url: Optional[str] = None  # S3 URL
    timestamp: datetime

