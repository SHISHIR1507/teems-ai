from datetime import datetime
from typing import Optional, List, Dict, Any
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
    # Whether this agent is already assigned to the currently authenticated user.
    # This is populated at runtime in the router by looking up AgentAssignment rows.
    is_assigned_to_current_user: bool = Field(
        default=False,
        description="True if this agent is assigned to the requesting user in their tenant",
    )

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


class AgentAssignmentRequest(BaseModel):
    """
    Kept for backwards compatibility, but the assign endpoint now derives
    tenant_id and user_id from the authenticated context instead of this body.
    """

    tenant_id: Optional[str] = Field(
        default=None,
        description="(Deprecated) Tenant identifier; ignored by the API",
    )
    user_id: Optional[str] = Field(
        default=None,
        description="(Deprecated) User who is adding the agent; ignored by the API",
    )


class AgentAssignmentResponse(BaseModel):
    id: uuid_pkg.UUID
    agent_id: uuid_pkg.UUID
    tenant_id: Optional[str]
    user_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AgentRunRequest(BaseModel):
    tenant_id: Optional[str] = Field(default=None, description="Tenant identifier for the run")
    user_id: Optional[str] = Field(default=None, description="User who triggered the run")
    input_payload: Dict[str, Any] = Field(default_factory=dict, description="Execution input/prompt/context")


class AgentRunResponse(BaseModel):
    id: uuid_pkg.UUID
    agent_id: uuid_pkg.UUID
    status: str
    tenant_id: Optional[str]
    user_id: Optional[str]
    input_payload: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True