"""
Database configuration and models for Social Media Agent
Uses SQLAlchemy with async PostgreSQL (asyncpg)
"""
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, JSON, Integer
from datetime import datetime
from app.core.config import get_settings

# Lazy initialization pattern (like presentation)
engine = None
async_session_maker: Optional[async_sessionmaker[AsyncSession]] = None


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
    """Stores conversation metadata and flow state"""
    __tablename__ = "social_media_conversations"
    
    id = Column(String, primary_key=True)  # UUID
    tenant_id = Column(String, nullable=False, index=True)  # Tenant ID from Auth0
    user_id = Column(String, nullable=True)  # Auth0 sub (for reference)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Flow state: collect_content | prepare_and_confirm | post | success | error
    stage = Column(String(32), nullable=False, default="collect_content")
    pending_asset_id = Column(String, nullable=True)  # FK to content_assets
    suggested_caption = Column(Text, nullable=True)
    suggested_hashtags = Column(Text, nullable=True)  # JSON array as string
    pending_platforms = Column(Text, nullable=True)  # JSON array as string, e.g. ["tiktok"]
    last_error = Column(Text, nullable=True)
    
    # Relationships
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    posts = relationship("Post", back_populates="conversation", cascade="all, delete-orphan")
    assets = relationship("ContentAsset", back_populates="conversation", cascade="all, delete-orphan")


class ContentAsset(Base):
    """Uploaded or linked content (image/video) for posting"""
    __tablename__ = "social_media_content_assets"
    
    id = Column(String, primary_key=True)  # UUID
    conversation_id = Column(String, ForeignKey("social_media_conversations.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=True)
    asset_type = Column(String(16), nullable=False)  # 'image' | 'video'
    source = Column(String(16), nullable=False)  # 'upload' | 'link'
    s3_key = Column(String, nullable=True)
    s3_url = Column(String, nullable=True)
    external_url = Column(Text, nullable=True)  # when source=link
    file_name = Column(String, nullable=True)
    content_type = Column(String(128), nullable=True)
    vision_analysis = Column(Text, nullable=True)  # GPT-4o Vision analysis result
    created_at = Column(DateTime, default=datetime.utcnow)
    
    conversation = relationship("Conversation", back_populates="assets")


class Message(Base):
    """Stores conversation messages"""
    __tablename__ = "social_media_messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String, ForeignKey("social_media_conversations.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    conversation = relationship("Conversation", back_populates="messages")


class UserToken(Base):
    """Store social media platform access tokens for users"""
    __tablename__ = "social_media_user_tokens"

    tenant_id = Column(String, nullable=False, primary_key=True)  # Tenant ID from Auth0
    platform = Column(String(50), nullable=False, primary_key=True)  # 'tiktok', 'facebook', etc.
    user_id = Column(String, nullable=True)  # Auth0 sub (for reference)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)  # For token refresh
    platform_user_id = Column(String, nullable=True)  # Platform-specific user ID (e.g., TikTok open_id)
    expires_at = Column(DateTime, nullable=True)  # Token expiration
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Post(Base):
    """Track posted social media content"""
    __tablename__ = "social_media_posts"

    id = Column(String, primary_key=True)  # UUID
    conversation_id = Column(String, ForeignKey("social_media_conversations.id", ondelete="SET NULL"), nullable=True)
    tenant_id = Column(String, nullable=False, index=True)  # Tenant ID from Auth0
    user_id = Column(String, nullable=True)  # Auth0 sub (for reference)
    platform = Column(String(50), default="tiktok", nullable=False, index=True)
    video_url = Column(Text, nullable=False)
    caption = Column(Text, nullable=True)
    hashtags = Column(Text, nullable=True)  # Comma-separated
    status = Column(String(20), default="posted", nullable=False)  # scheduled, pending, posted, failed, processing
    scheduled_at = Column(DateTime(timezone=True), nullable=True, index=True)  # When to post (if scheduled)
    publish_id = Column(Text, nullable=True)  # Platform-specific publish ID
    extra = Column(JSON, nullable=True)  # Additional platform-specific data
    error = Column(Text, nullable=True)  # Error message if failed
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship
    conversation = relationship("Conversation", back_populates="posts")


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
