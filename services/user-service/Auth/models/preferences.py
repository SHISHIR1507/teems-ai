from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, String, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .user import Base


class UserPreferences(Base):
    __tablename__ = "user_preferences"
    
    # user_id is both ForeignKey AND PrimaryKey
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False
    )
    
    notification_frequency: Mapped[str] = mapped_column(
        String(20), 
        default="daily", 
        nullable=False
    )
    notification_channels: Mapped[list[str]] = mapped_column(
        JSON, 
        default=list, 
        nullable=False
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=text("CURRENT_TIMESTAMP")
    )
    
    user: Mapped["User"] = relationship(
        "User", 
        back_populates="preferences"
    )