from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID

from ..database.base import Base


class Agent(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    owner_user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    name = Column(String(200), nullable=False)
    visibility = Column(String(32), default="private", nullable=False)
    meta_data = Column(JSON, name="metadata", nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class AgentVersion(Base):
    __tablename__ = "agent_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(String(32), nullable=False)
    manifest = Column(JSON, nullable=True)
    checksum = Column(String(128), nullable=True)
    lifecycle = Column(String(32), default="active", nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class AgentExecution(Base):
    __tablename__ = "agent_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    agent_version_id = Column(UUID(as_uuid=True), ForeignKey("agent_versions.id", ondelete="CASCADE"), nullable=False)
    initiator_user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    status = Column(String(32), nullable=False)
    input_payload = Column(JSON, nullable=True)
    output_payload = Column(JSON, nullable=True)
    logs_s3_url = Column(String(512), nullable=True)
    error = Column(JSON, nullable=True)
    started_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)

