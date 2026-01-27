"""
Database configuration and models for UGC Orchestrator
Uses SQLAlchemy with async PostgreSQL (asyncpg)
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, JSON, Integer, Index
from datetime import datetime
from app.core.config import get_settings

# Lazy initialization pattern (like presentation service)
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
    __tablename__ = "ugc_conversations"  # Changed to avoid conflicts with existing table
    
    id = Column(String, primary_key=True)  # UUID
    tenant_id = Column(String, nullable=False, index=True)  # Tenant ID from Auth0
    user_id = Column(String, nullable=True)  # Auth0 sub (for reference)
    brand_industry = Column(String, nullable=True)
    brand_audience = Column(String, nullable=True)
    brand_vibe = Column(String, nullable=True)
    brand_locked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    assets = relationship("Asset", back_populates="conversation", cascade="all, delete-orphan")
    
    # Index on tenant_id for performance
    __table_args__ = (Index('idx_ugc_conversations_tenant_id', 'tenant_id'),)


class Message(Base):
    """Stores conversation messages"""
    __tablename__ = "ugc_messages"  # Changed to avoid conflicts
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String, ForeignKey("ugc_conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    conversation = relationship("Conversation", back_populates="messages")


class Asset(Base):
    """Stores generated assets (images, audio, videos, scripts)"""
    __tablename__ = "ugc_assets"  # Changed to avoid conflicts
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String, ForeignKey("ugc_conversations.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String, nullable=False, index=True)  # Tenant ID from Auth0
    user_id = Column(String, nullable=True)  # Auth0 sub (for reference)
    asset_type = Column(String, nullable=False)  # 'uploaded_person', 'uploaded_product', 'generated_image', 'audio', 'video', 'script'
    url = Column(Text, nullable=False)  # S3 URL or AIML API URL
    filename = Column(String, nullable=True)  # Original filename
    asset_metadata = Column(JSON, nullable=True)  # Additional metadata (size, duration, etc.) - renamed from 'metadata'
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    conversation = relationship("Conversation", back_populates="assets")
    
    # Index on tenant_id for performance
    __table_args__ = (Index('idx_ugc_assets_tenant_id', 'tenant_id'),)


# Initialize database tables
async def init_db():
    """Create all tables in the database (only creates if they don't exist)"""
    eng = init_engine()
    async with eng.begin() as conn:
        # create_all() only creates tables that don't exist yet
        # It will NOT drop or modify existing tables
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
