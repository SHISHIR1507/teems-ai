"""
SQLAlchemy models for conversations and messages tables.
"""
from sqlalchemy import Column, String, Integer, Text, ForeignKey, JSON, TIMESTAMP, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from ..database.base import Base


class Conversation(Base):
    """Conversation model - maps to 'eve_conversations' table."""
    
    __tablename__ = "eve_conversations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(128), nullable=False, index=True)
    session_id = Column(String(255), nullable=False, index=True)
    user_id = Column(String(255), nullable=True)
    title = Column(String(255), nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.sequence_number"
    )
    
    # Unique constraint: one conversation per tenant+session
    __table_args__ = (
        UniqueConstraint('tenant_id', 'session_id', name='uq_eve_conversations_tenant_session'),
    )
    
    def __repr__(self):
        return f"<Conversation(id={self.id}, tenant_id={self.tenant_id}, session_id={self.session_id})>"


class Message(Base):
    """Message model - maps to 'eve_messages' table."""
    
    __tablename__ = "eve_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("eve_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(128), nullable=False, index=True)
    role = Column(String(50), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    metadata = Column(JSON, nullable=True)  # Optional metadata (tool calls, recommendations, etc.)
    sequence_number = Column(Integer, nullable=False)  # Message order within conversation
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    
    # Relationship
    conversation = relationship("Conversation", back_populates="messages")
    
    # Index for ordered retrieval
    __table_args__ = (
        {'mysql_engine': 'InnoDB'}  # This is a placeholder, PostgreSQL doesn't need this
    )
    
    def __repr__(self):
        return f"<Message(id={self.id}, conversation_id={self.conversation_id}, role={self.role}, seq={self.sequence_number})>"
