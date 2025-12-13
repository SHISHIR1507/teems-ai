from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IntegrationCreate(BaseModel):
    integration_type: str = Field(..., description="Integration type: slack, google_drive, notion, github, etc.")
    metadata: dict[str, Any] | None = Field(None, description="Integration metadata/tokens")


class IntegrationResponse(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    integration_type: str
    status: str
    metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

