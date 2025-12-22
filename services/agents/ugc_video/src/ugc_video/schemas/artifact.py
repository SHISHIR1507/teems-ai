from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid as uuid_pkg


class ArtifactResponse(BaseModel):
    id: uuid_pkg.UUID
    artifact_type: str
    s3_url: Optional[str] = None
    metadata: dict
    created_at: datetime

    class Config:
        from_attributes = True

