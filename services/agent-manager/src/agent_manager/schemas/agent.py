from datetime import datetime
from typing import Optional, List
import uuid as uuid_pkg
from pydantic import BaseModel, Field


# Base schema with common fields
class AgentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    short_description: Optional[str] = Field(None, max_length=200)
    category: Optional[str] = None
    price: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    tools_stack: List[str] = Field(default_factory=list)


# For creating new agent (POST request)
class AgentCreate(AgentBase):
    pass


# For updating agent (PUT/PATCH request)
class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    short_description: Optional[str] = Field(None, max_length=200)
    category: Optional[str] = None
    price: Optional[str] = None
    skills: Optional[List[str]] = None
    tools_stack: Optional[List[str]] = None
    version: Optional[int] = None


# For agent in list view (GET /agents)
class AgentListItem(BaseModel):
    id: uuid_pkg.UUID
    name: str
    title: str
    short_description: Optional[str]
    category: Optional[str]
    price: Optional[str]
    skills: List[str]
    # profile_image_url: Optional[str] = None  # Will add when S3 ready
    created_at: datetime
    
    class Config:
        from_attributes = True


# For single agent detail view (GET /agents/{id})
class AgentResponse(AgentBase):
    id: uuid_pkg.UUID
    version: int
    # profile_image_url: Optional[str] = None  # Will add when S3 ready
    # hero_image_url: Optional[str] = None     # Will add when S3 ready
    # intro_video_url: Optional[str] = None    # Will add when S3 ready
    # sample_work_urls: List[str] = Field(default_factory=list)  # Will add when S3 ready
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Response for GET /agents (list endpoint)
class AgentListResponse(BaseModel):
    agents: List[AgentListItem]
    total: int
    page: int
    size: int