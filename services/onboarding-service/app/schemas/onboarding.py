from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OnboardingStateResponse(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    current_stage: str
    conversation_id: str
    brand_domain: str | None = None
    selected_teammates: list[str] | None = None
    connected_integrations: list[str] | None = None
    notification_preferences: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

