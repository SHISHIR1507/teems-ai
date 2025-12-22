from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from ..database.base import Base


class ArtifactType(str, enum.Enum):
    IMAGE = "image"
    VIDEO = "video"
    SCRIPT = "script"


class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    artifact_type = Column(SQLEnum(ArtifactType), nullable=False)
    s3_key = Column(String(500), nullable=False)
    s3_url = Column(String(1000), nullable=True)  # Presigned URL or public URL
    metadata = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="artifacts")

    def __repr__(self):
        return f"<Artifact(id={self.id}, conversation_id={self.conversation_id}, type={self.artifact_type})>"

