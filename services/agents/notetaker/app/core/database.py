"""
Database configuration and models for Notetaker Agent
Uses SQLAlchemy with async PostgreSQL (asyncpg) and pgvector
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from app.core.config import get_settings
from app.models.call import Base, UserSettings, CalendarEvent

# Lazy initialization pattern (like presentation service)
engine = None
async_session_maker: async_sessionmaker[AsyncSession] | None = None


def init_engine():
    """Initialize database engine (lazy initialization)"""
    global engine, async_session_maker
    if engine is None:
        settings = get_settings()
        database_url = settings.database_url
        
        # Ensure DATABASE_URL uses asyncpg driver
        if database_url.startswith("postgresql://") and "+asyncpg" not in database_url:
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif not database_url.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection string")
        
        engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=3600,
            connect_args={
                "server_settings": {
                    "application_name": "notetaker_service",
                },
                "command_timeout": 10,
                "timeout": 10,
            }
        )
        async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    return engine


# Initialize database tables
async def init_db():
    """Create all tables in the database (only creates if they don't exist)"""
    eng = init_engine()
    async with eng.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables created successfully (existing tables preserved)")


# Drop all tables (use with caution!)
async def drop_db():
    """Drop all tables in the database"""
    eng = init_engine()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("⚠️ All database tables dropped")


# Legacy get_db for backward compatibility during migration
async def get_db():
    """Legacy dependency for FastAPI endpoints (use get_db_session instead)"""
    if async_session_maker is None:
        init_engine()
    assert async_session_maker is not None
    async with async_session_maker() as session:
        yield session
