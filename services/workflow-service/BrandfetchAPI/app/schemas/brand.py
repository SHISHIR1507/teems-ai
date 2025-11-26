from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class BrandFetchRequest(BaseModel):
    url: str = Field(..., description="Website URL or domain, e.g. 'slack.com'")
    force_refresh: bool = Field(
        default=False,
        description="When true, bypass cached DB record and hit Brandfetch again",
    )

    @field_validator("url")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("URL cannot be empty")
        return value.strip()


class BrandSummary(BaseModel):
    domain: str
    name: str | None = None
    icon: str | None = None
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class BrandRecordResponse(BrandSummary):
    details: dict[str, Any]


class BrandFetchResponse(BrandRecordResponse):
    source: str = Field(description="Where the data came from", default="cache")

