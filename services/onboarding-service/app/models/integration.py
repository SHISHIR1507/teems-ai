from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, String, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..database.base import Base


class UserIntegration(Base):
    __tablename__ = "user_integrations"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    integration_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # slack, google_drive, notion, github, etc.
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="connected"
    )  # connected, disconnected
    metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )  # For tokens/credentials (encrypted in production)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

