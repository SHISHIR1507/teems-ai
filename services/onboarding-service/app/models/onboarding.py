from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, String, Text, TIMESTAMP, func, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..database.base import Base


class OnboardingState(Base):
    __tablename__ = "onboarding_states"
    __table_args__ = (
        # Composite index for common query pattern: conversation_id + tenant_id
        Index("ix_onboarding_conv_tenant", "conversation_id", "tenant_id"),
        # Index for querying by tenant and stage
        Index("ix_onboarding_tenant_stage", "tenant_id", "current_stage"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    current_stage: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="brand_discovery",
        index=True,
    )  # brand_discovery, suggested_teammates, connect_world, personalization, completed
    conversation_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), nullable=False, unique=True, index=True, default=lambda: str(uuid4())
    )
    brand_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    selected_teammates: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    connected_integrations: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True
    )
    notification_preferences: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    extra_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default=text("'{}'::json"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        # Composite index for fetching conversation history efficiently
        Index("ix_conversation_conv_created", "conversation_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    conversation_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("onboarding_states.conversation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

