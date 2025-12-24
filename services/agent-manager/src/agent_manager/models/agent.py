from datetime import datetime
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from ..database.base import Base


class Agent(Base):
    """
    Catalogue entry for a Teem Mate / agent.

    This model is designed to back the rich agent identity structure used in the
    product UI (e.g. Molly/Mila/Chad examples), so we store:
    - core identity: name/title/about (mapped from teem_mate_name/teem_mate_role/about)
    - pricing and categorisation (category, price/monthly_rate, role_type)
    - skills list
    - tools stack as a JSON array of objects: [{ "label": ..., "icon": ... }, ...]
    - "works well with" relationships as a JSON array of objects:
      [{ "id": ..., "name": ..., "role": ..., "role_type": ... }, ...]
    - display image URL used by the frontend cards/detail pages
    """

    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Core identity
    name = Column(String(100), nullable=False)
    title = Column(String(100), nullable=False)  # e.g., "UGC Creator", "Fashion Photographer"
    description = Column(Text, nullable=True)  # Full bio / "about" text for detail page
    short_description = Column(String(200), nullable=True)  # For card view

    # Display + categorisation
    category = Column(String(50), nullable=True)  # "Marketing", "Design", "Software"
    price = Column(String(50), nullable=True)  # Legacy/general price field ("$5000", "Contact for quote")
    monthly_rate = Column(String(50), nullable=True)  # "$50/month" as used in the examples
    role_type = Column(String(50), nullable=True)  # "creative", "marketing", etc.
    teem_mate_image = Column(String(500), nullable=True)  # e.g. "/images/teem_mate_ugc_creator.png"

    # Skills and tools
    skills = Column(JSON, nullable=True, default=list)  # ["Image-to-Video Generation", ...]
    # [{ "label": "Klaviyo", "icon": "slack_icon" }, ...]
    tools_stack = Column(JSON, nullable=True, default=list)

    # "Works well with" relationships (stored denormalised for now)
    # [
    #   { "id": "photo-01", "name": "Mila", "role": "Fashion Photographer", "role_type": "creative" },
    #   ...
    # ]
    works_well_with = Column(JSON, nullable=True, default=list)

    # Versioning
    version = Column(Integer, default=1, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<Agent(name={self.name}, title={self.title})>"


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(255), nullable=True, index=True)
    user_id = Column(String(255), nullable=True, index=True)
    status = Column(String(50), nullable=False, default="queued")
    input_payload = Column(JSON, nullable=True, default=dict)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<AgentRun(agent_id={self.agent_id}, status={self.status})>"


class AgentAssignment(Base):
    __tablename__ = "agent_assignments"
    __table_args__ = (
        UniqueConstraint("agent_id", "tenant_id", "user_id", name="uq_agent_assignment"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(255), nullable=True, index=True)
    user_id = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<AgentAssignment(agent_id={self.agent_id}, tenant_id={self.tenant_id}, user_id={self.user_id})>"