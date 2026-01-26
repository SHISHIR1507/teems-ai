"""
Database configuration and models for Fashion Photo Agent
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


class FashionSession(Base):
    """Stores fashion photo session metadata and workflow state"""
    __tablename__ = "fashion_sessions"
    
    id = Column(String, primary_key=True)  # UUID
    tenant_id = Column(String, nullable=False, index=True)  # Tenant ID from Auth0
    user_id = Column(String, nullable=True)  # Auth0 sub (for reference)
    stage = Column(String, nullable=False, default="CONVERSATION")  # CONVERSATION, APPAREL_SELECTION, AVATAR_SELECTION, SCENE_SUGGESTION, SCENE_CONFIRMATION, GENERATION, EDITING
    metadata = Column(JSON, nullable=True)  # suggested_scene, awaiting_scene_confirmation, last_generation_batch_id, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    avatars = relationship("Avatar", back_populates="session", cascade="all, delete-orphan")
    apparel = relationship("Apparel", back_populates="session", cascade="all, delete-orphan")
    generated_images = relationship("GeneratedImage", back_populates="session", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="session", cascade="all, delete-orphan")


class Avatar(Base):
    """Stores uploaded or selected avatars"""
    __tablename__ = "fashion_avatars"
    
    id = Column(String, primary_key=True)  # UUID
    session_id = Column(String, ForeignKey("fashion_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=True)
    s3_url = Column(String, nullable=False)
    s3_key = Column(String, nullable=False)
    avatar_type = Column(String, nullable=False, default="uploaded")  # uploaded, preset
    preset_url = Column(String, nullable=True)  # If preset, original URL
    avatar_analysis = Column(Text, nullable=True)  # Vision analysis: build, skin, face, hair, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    session = relationship("FashionSession", back_populates="avatars")


class Apparel(Base):
    """Stores uploaded apparel images"""
    __tablename__ = "fashion_apparel"
    
    id = Column(String, primary_key=True)  # UUID
    session_id = Column(String, ForeignKey("fashion_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=True)
    s3_url = Column(String, nullable=False)
    s3_key = Column(String, nullable=False)
    filename = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    content_type = Column(String, nullable=True)
    vision_analysis = Column(Text, nullable=True)  # GPT-4o Vision analysis result
    metadata = Column(JSON, nullable=True)  # Additional metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    session = relationship("FashionSession", back_populates="apparel")


class GeneratedImage(Base):
    """Stores generated fashion images"""
    __tablename__ = "fashion_generated_images"
    
    id = Column(String, primary_key=True)  # UUID
    session_id = Column(String, ForeignKey("fashion_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=True)
    s3_url = Column(String, nullable=False)
    s3_key = Column(String, nullable=False)
    angle = Column(String, nullable=True)  # Front View, Back View, Side Profile, etc.
    scene = Column(String, nullable=True)  # Scene description used
    prompt = Column(Text, nullable=True)  # Full prompt used
    generation_metadata = Column(JSON, nullable=True)  # Model, parameters, etc.
    task_id = Column(String, nullable=True)  # Reference to Task if async
    batch_id = Column(String, nullable=True, index=True)  # Groups images per generation/edit batch
    generation_type = Column(String, nullable=False, default="initial")  # initial | edit
    edit_instruction = Column(Text, nullable=True)  # User edit request when generation_type=edit
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    session = relationship("FashionSession", back_populates="generated_images")


class Message(Base):
    """Stores conversation messages"""
    __tablename__ = "fashion_messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("fashion_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    session = relationship("FashionSession", back_populates="messages")


class Task(Base):
    """Stores async task information"""
    __tablename__ = "fashion_tasks"
    
    id = Column(String, primary_key=True)  # UUID
    session_id = Column(String, ForeignKey("fashion_sessions.id", ondelete="CASCADE"), nullable=True, index=True)
    tenant_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=True)
    task_type = Column(String, nullable=False)  # image_generation, scene_suggestion, vision_analysis
    status = Column(String, nullable=False, default="pending")  # pending, processing, completed, failed
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    metadata = Column(JSON, nullable=True)  # Task-specific metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    session = relationship("FashionSession", back_populates="tasks")


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
