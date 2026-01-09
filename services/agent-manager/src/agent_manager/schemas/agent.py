from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid as uuid_pkg

from pydantic import BaseModel, Field


class ToolStackItem(BaseModel):
    """
    Represents one entry in an agent's tools stack, mirroring the frontend shape:
    { "label": "Klaviyo", "icon": "slack_icon" }

    The `icon` is a string identifier that the frontend can map to an actual asset/component.
    """

    label: str
    icon: Optional[str] = Field(
        default=None,
        description="Identifier used by the frontend to resolve the icon (e.g. 'slack_icon')",
    )


class WorksWellWithItem(BaseModel):
    """
    Represents one 'works well with' relationship for an agent:
    { 
      "id": "photo-01", 
      "name": "Mila", 
      "role": "Fashion Photographer", 
      "role_type": "creative",
      "image": "https://s3.../teem_mate_fashion_photographer.png"
    }
    
    The frontend can use the `id` to fetch full agent details when clicked.
    """

    id: str = Field(..., description="Agent ID (UUID as string) - use this to fetch full agent details")
    name: str
    role: str
    role_type: str
    image: Optional[str] = Field(
        default=None,
        description="URL or path to the agent's image (e.g., teem_mate_image from the agent)"
    )


class WorkSample(BaseModel):
    """
    Represents a work sample/portfolio item for an agent:
    {
      "title": "Glow Boost Campaign",
      "client": "Glow Skincare",
      "description": "Launched a 12-email skincare education series...",
      "image": "https://s3.../work_sample_1.png"
    }
    """

    title: str
    client: str
    description: str
    image: str = Field(..., description="URL to the work sample image")


# Base schema with common fields
class AgentBase(BaseModel):
    # These map directly to the examples:
    # - teem_mate_name -> name
    # - teem_mate_role -> title
    # - about -> description
    name: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    short_description: Optional[str] = Field(None, max_length=200)

    # Categorisation + pricing
    category: Optional[str] = None
    price: Optional[str] = None  # legacy/general pricing
    monthly_rate: Optional[str] = Field(
        default=None,
        description="Human-readable monthly rate, e.g. '$50/month'",
    )
    role_type: Optional[str] = Field(
        default=None,
        description="High-level role type such as 'creative' or 'marketing'",
    )

    # Display image used on cards/detail (e.g. '/images/teem_mate_ugc_creator.png')
    teem_mate_image: Optional[str] = Field(
        default=None,
        description="Path or URL to the primary image representing the agent",
    )

    # Skills and tools
    skills: List[str] = Field(default_factory=list)
    tools_stack: List[ToolStackItem] = Field(
        default_factory=list,
        description="Tools the agent works with, including a label and an icon identifier",
    )

    # "Works well with" relationships
    works_well_with: List[WorksWellWithItem] = Field(
        default_factory=list,
        description=(
            "Other agents this one works well with; "
            "list of {id, name, role, role_type} objects. "
            "Frontend can use the `id` field to fetch full agent details when clicked."
        ),
    )

    # Work samples/portfolio items
    work_samples: List[WorkSample] = Field(
        default_factory=list,
        description="Portfolio/showcase work samples for this agent",
    )


class AgentCreate(AgentBase):
    """Payload for creating a new agent."""

    pass


class AgentUpdate(BaseModel):
    """Partial update for an agent."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    short_description: Optional[str] = Field(None, max_length=200)

    category: Optional[str] = None
    price: Optional[str] = None
    monthly_rate: Optional[str] = Field(
        default=None,
        description="Human-readable monthly rate, e.g. '$50/month'",
    )
    role_type: Optional[str] = Field(
        default=None,
        description="High-level role type such as 'creative' or 'marketing'",
    )
    teem_mate_image: Optional[str] = Field(
        default=None,
        description="Path or URL to the primary image representing the agent",
    )

    skills: Optional[List[str]] = None
    tools_stack: Optional[List[ToolStackItem]] = None
    works_well_with: Optional[List[WorksWellWithItem]] = None
    work_samples: Optional[List[WorkSample]] = None

    version: Optional[int] = None


class AgentListItem(BaseModel):
    """Shape returned from the list endpoint for each agent."""

    id: uuid_pkg.UUID
    name: str
    title: str
    short_description: Optional[str]
    category: Optional[str]
    price: Optional[str]
    monthly_rate: Optional[str]
    role_type: Optional[str]
    teem_mate_image: Optional[str]
    skills: List[str]
    tools_stack: List[ToolStackItem]
    works_well_with: List[WorksWellWithItem]
    work_samples: List[WorkSample]
    created_at: datetime

    # Whether this agent is already assigned to the currently authenticated user.
    # This is populated at runtime in the router by looking up AgentAssignment rows.
    is_assigned_to_current_user: bool = Field(
        default=False,
        description="True if this agent is assigned to the requesting user in their tenant",
    )

    class Config:
        from_attributes = True


class AgentResponse(AgentBase):
    """
    Detailed representation of an agent returned from the detail endpoint.

    Extends AgentBase with versioning and timestamps, plus the
    `is_assigned_to_current_user` flag used by the UI.
    """

    id: uuid_pkg.UUID
    version: int
    created_at: datetime
    updated_at: datetime

    # Keep this aligned with AgentListItem so the detail view also exposes whether
    # the agent is already assigned to the requesting user.
    is_assigned_to_current_user: bool = Field(
        default=False,
        description="True if this agent is assigned to the requesting user in their tenant",
    )

    class Config:
        from_attributes = True


class AgentListResponse(BaseModel):
    """Envelope for the paginated agent list endpoint."""

    agents: List[AgentListItem]
    total: int
    page: int
    size: int


class AgentCategoriesResponse(BaseModel):
    """
    Simple response model for the categories endpoint.

    Returns the distinct non-null agent categories currently present
    in the catalogue.
    """

    categories: List[str]


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
    tenant_id: Optional[str] = Field(
        default=None,
        description="Tenant identifier for the run (deprecated; derived from auth context)",
    )
    user_id: Optional[str] = Field(
        default=None,
        description="User who triggered the run (deprecated; derived from auth context)",
    )
    input_payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Execution input/prompt/context",
    )


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