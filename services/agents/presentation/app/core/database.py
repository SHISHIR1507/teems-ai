"""
Database configuration and models for Presentation Agent
Uses SQLAlchemy with async PostgreSQL (asyncpg)
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, JSON, Integer
from datetime import datetime
from app.core.config import get_settings

# Lazy initialization pattern (like eve-core)
engine = None
async_session_maker: async_sessionmaker[AsyncSession] | None = None


def init_engine():
    """Initialize database engine (lazy initialization)"""
    global engine, async_session_maker
    if engine is None:
        settings = get_settings()
        engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20
        )
        async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    return engine

# Base class for models
Base = declarative_base()


class Conversation(Base):
    """Stores conversation metadata and brand context"""
    __tablename__ = "presentation_conversations"
    
    id = Column(String, primary_key=True)  # UUID
    tenant_id = Column(String, nullable=False, index=True)  # Tenant ID from Auth0
    user_id = Column(String, nullable=True)  # Auth0 sub (for reference)
    brand_locked = Column(Boolean, default=False)
    brand_logo_url = Column(String, nullable=True)
    brand_primary_color = Column(String, nullable=True)
    brand_secondary_color = Column(String, nullable=True)
    brand_font = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    presentations = relationship("Presentation", back_populates="conversation", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    """Stores conversation messages"""
    __tablename__ = "presentation_messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String, ForeignKey("presentation_conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    conversation = relationship("Conversation", back_populates="messages")


class Presentation(Base):
    """Stores generated presentations"""
    __tablename__ = "presentations"
    
    id = Column(String, primary_key=True)  # UUID
    conversation_id = Column(String, ForeignKey("presentation_conversations.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String, nullable=False, index=True)  # Tenant ID from Auth0
    user_id = Column(String, nullable=True)  # Auth0 sub (for reference)
    slidespeak_presentation_id = Column(String, nullable=True)
    slidespeak_task_id = Column(String, nullable=True)
    title = Column(String, nullable=True)
    s3_url = Column(String, nullable=True)
    s3_key = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")  # pending, processing, completed, failed
    metadata = Column(JSON, nullable=True)  # length, template, tone, etc.
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    conversation = relationship("Conversation", back_populates="presentations")


class Document(Base):
    """Stores uploaded documents"""
    __tablename__ = "presentation_documents"
    
    id = Column(String, primary_key=True)  # UUID
    conversation_id = Column(String, ForeignKey("presentation_conversations.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String, nullable=False, index=True)  # Tenant ID from Auth0
    user_id = Column(String, nullable=True)  # Auth0 sub (for reference)
    filename = Column(String, nullable=False)
    s3_url = Column(String, nullable=False)
    s3_key = Column(String, nullable=False)
    slidespeak_document_id = Column(String, nullable=True)
    processing_status = Column(String, nullable=False, default="uploaded")  # uploaded, processing, ready, failed
    file_size = Column(Integer, nullable=True)
    content_type = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    conversation = relationship("Conversation", back_populates="documents")


class Task(Base):
    """Stores async task information"""
    __tablename__ = "presentation_tasks"
    
    id = Column(String, primary_key=True)  # UUID
    tenant_id = Column(String, nullable=False, index=True)  # Tenant ID from Auth0
    user_id = Column(String, nullable=True)  # Auth0 sub (for reference)
    conversation_id = Column(String, nullable=True)
    task_type = Column(String, nullable=False)  # generate, edit, upload
    slidespeak_task_id = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")  # pending, processing, completed, failed
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Initialize database tables
async def init_db():
    """Create all tables in the database (only creates if they don't exist)"""
    eng = init_engine()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables created successfully (existing tables preserved)")


# Drop all tables (use with caution!)
async def drop_db():
    """Drop all tables in the database"""
    eng = init_engine()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("⚠️ All database tables dropped")


if __name__ == "__main__":
    import asyncio
    
    async def main():
        print("Initializing database...")
        await init_db()
    
    asyncio.run(main())
