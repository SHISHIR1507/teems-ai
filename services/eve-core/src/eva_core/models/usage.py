from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, JSON, Numeric, String
from sqlalchemy.dialects.postgresql import UUID

from ..database.base import Base


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    event_id = Column(String(128), nullable=True)
    service = Column(String(64), nullable=True)
    operation = Column(String(64), nullable=True)
    provider = Column(String(64), nullable=True)
    model = Column(String(128), nullable=True)
    input_tokens = Column(String(64), nullable=True)
    output_tokens = Column(String(64), nullable=True)
    cost_estimate = Column(Numeric(10, 6), nullable=True)
    raw = Column(JSON, nullable=True)
    billed = Column(String(8), default="false", nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class BillingLedger(Base):
    __tablename__ = "billing_ledger"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    usage_event_id = Column(UUID(as_uuid=True), nullable=True)
    invoice_id = Column(UUID(as_uuid=True), nullable=True)
    amount = Column(Numeric(10, 2), nullable=True)
    currency = Column(String(8), default="USD", nullable=False)
    description = Column(String(256), nullable=True)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

