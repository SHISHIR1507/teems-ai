"""
Database models for Notetaker Agent
"""
from sqlalchemy import Column, String, Text, JSON, DateTime, ForeignKey, Integer, Index, Boolean
from sqlalchemy.orm import DeclarativeBase, relationship
from pgvector.sqlalchemy import Vector
import uuid
from datetime import datetime

class Base(DeclarativeBase):
    pass

class Call(Base):
    """Stores meeting/call information with tenant isolation"""
    __tablename__ = "notetaker_calls"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, nullable=False, index=True)  # Tenant ID from Auth0
    user_id = Column(String, nullable=True)  # Auth0 sub (for reference)
    meeting_id = Column(String, nullable=True, index=True)  # Nylas meeting ID
    calendar_event_id = Column(String, ForeignKey("notetaker_calendar_events.id", ondelete="SET NULL"), nullable=True, index=True)  # FK to CalendarEvent
    title = Column(String, nullable=False)
    meeting_link = Column(Text, nullable=False)
    start_time = Column(DateTime, nullable=False)
    transcript = Column(Text, nullable=True)  # Clean text transcript
    summary = Column(Text, nullable=True)
    action_items = Column(JSON, nullable=True)  # Action items as JSON
    status = Column(String, nullable=False, default="scheduled")  # scheduled, processing, completed, failed
    auto_joined = Column(Boolean, nullable=False, default=False)  # Whether meeting was auto-joined
    join_attempted_at = Column(DateTime, nullable=True)  # When join was attempted
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    chunks = relationship("CallChunk", back_populates="call", cascade="all, delete-orphan")
    calendar_event = relationship("CalendarEvent", back_populates="call", foreign_keys=[calendar_event_id])
    
    # Indexes for better query performance
    __table_args__ = (
        Index("idx_notetaker_calls_tenant_created", "tenant_id", "created_at"),
    )


class CallChunk(Base):
    """Stores chunked transcript content with embeddings for RAG"""
    __tablename__ = "notetaker_call_chunks"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    call_id = Column(String, ForeignKey("notetaker_calls.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content_type = Column(String, nullable=False, default="transcript")  # 'transcript', 'summary', 'action_items'
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=False)  # PgVector type for semantic search
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    call = relationship("Call", back_populates="chunks")
    
    # Indexes for query performance and vector similarity search
    __table_args__ = (
        Index("idx_notetaker_call_chunks_call_id", "call_id"),
        Index("idx_notetaker_call_chunks_tenant_call", "tenant_id", "call_id"),
    )


class UserSettings(Base):
    """Stores user-specific settings including Google Calendar integration"""
    __tablename__ = "notetaker_user_settings"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, nullable=False, index=True)  # Tenant ID from Auth0
    user_id = Column(String, nullable=False, index=True)  # Auth0 sub
    timezone = Column(String, nullable=False, default="UTC")  # e.g., "America/New_York"
    google_calendar_enabled = Column(Boolean, nullable=False, default=False)
    google_calendar_id = Column(String, nullable=True)  # Google Calendar ID
    google_oauth_token = Column(Text, nullable=True)  # Encrypted OAuth token (JSON)
    google_oauth_refresh_token = Column(Text, nullable=True)  # Encrypted refresh token
    last_calendar_sync = Column(DateTime, nullable=True)  # Last successful sync time
    auto_join_enabled = Column(Boolean, nullable=False, default=False)  # Enable auto-join
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint on tenant_id + user_id
    __table_args__ = (
        Index("idx_notetaker_user_settings_tenant_user", "tenant_id", "user_id", unique=True),
    )


class CalendarEvent(Base):
    """Stores calendar events synced from Google Calendar"""
    __tablename__ = "notetaker_calendar_events"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, nullable=False, index=True)  # Tenant ID from Auth0
    user_id = Column(String, nullable=False, index=True)  # Auth0 sub
    google_event_id = Column(String, nullable=False, unique=True, index=True)  # Google Calendar event ID
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    start_time = Column(DateTime, nullable=False)  # UTC datetime
    end_time = Column(DateTime, nullable=False)  # UTC datetime
    meeting_link = Column(Text, nullable=True)  # Meeting URL if available
    meeting_platform = Column(String, nullable=True)  # "zoom", "teams", "google_meet", etc.
    status = Column(String, nullable=False, default="synced")  # synced, scheduled, joined, completed, failed
    call_id = Column(String, ForeignKey("notetaker_calls.id", ondelete="SET NULL"), nullable=True, index=True)  # FK to Call
    nylas_notetaker_id = Column(String, nullable=True)  # Nylas notetaker ID after join
    auto_join_attempted = Column(Boolean, nullable=False, default=False)  # Whether auto-join was attempted
    join_attempted_at = Column(DateTime, nullable=True)  # When join was attempted
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    call = relationship("Call", back_populates="calendar_event", foreign_keys=[call_id])
    
    # Indexes for better query performance
    __table_args__ = (
        Index("idx_notetaker_calendar_events_tenant_start", "tenant_id", "start_time"),
        Index("idx_notetaker_calendar_events_status", "status"),
    )
