from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class BrandFetchRequest(BaseModel):
    url: str = Field(..., description="Website URL or domain, e.g. 'slack.com'")
    force_refresh: bool = Field(
        default=False,
        description="When true, bypass cached DB record and hit Brandfetch again",
    )
    tenant_id: str | None = Field(
        default=None,
        description="Tenant identifier used for onboarding event channeling",
    )
    conversation_id: str | None = Field(
        default=None,
        description="Conversation identifier for correlating realtime events",
    )

    @field_validator("url")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("URL cannot be empty")
        return value.strip()


class BrandSummary(BaseModel):
    domain: str
    website_url: str | None = None
    name: str | None = None
    icon: str | None = None
    description: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    contact_address: str | None = None
    instagram_url: str | None = None
    youtube_url: str | None = None
    facebook_url: str | None = None
    industry: str | None = None
    language: str | None = None
    region: str | None = None
    tone_of_voice: str | None = None
    created_at: datetime
    updated_at: datetime


class BrandRecordResponse(BrandSummary):
    details: dict[str, Any]


class BrandFetchResponse(BrandRecordResponse):
    source: str = Field(description="Where the data came from", default="cache")


class BrandUpdateRequest(BaseModel):
    name: str | None = None
    website_url: str | None = None
    description: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    contact_address: str | None = None
    instagram_url: str | None = None
    youtube_url: str | None = None
    facebook_url: str | None = None
    industry: str | None = None
    language: str | None = None
    region: str | None = None
    tone_of_voice: str | None = None

