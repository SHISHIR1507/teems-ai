from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict



NotificationFrequency = Literal["daily", "weekly", "important_only"]
NotificationChannel = Literal["slack", "whatsapp", "email"]


class UserPreferencesBase(BaseModel):
    notification_frequency: NotificationFrequency = Field(
        default="daily",
        description="How often to receive notifications"
    )
    notification_channels: list[NotificationChannel] = Field(
        default_factory=lambda: ["email"],
        description="Where to receive notifications"
    )


class UserPreferencesUpdate(UserPreferencesBase):
    pass


class UserPreferencesResponse(UserPreferencesBase):
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    id: UUID
    auth0_user_id: str
    email: str
    name: str | None
    tenant_id: str | None
    notification_frequency: NotificationFrequency
    notification_channels: list[NotificationChannel]
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)