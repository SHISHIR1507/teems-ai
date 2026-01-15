from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text
from app.core.config import settings
from app.models.call import Base

if not settings.DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment variables")

# Ensure DATABASE_URL uses asyncpg driver
database_url = settings.DATABASE_URL
if database_url.startswith("postgresql://") and "+asyncpg" not in database_url:
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif not database_url.startswith("postgresql+asyncpg://"):
    raise ValueError("DATABASE_URL must be a PostgreSQL connection string")

engine = create_async_engine(
    database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=10,        # Number of connections to maintain
    max_overflow=20,     # Maximum overflow connections
    pool_timeout=30,     # Wait up to 30s for connection from pool
    pool_recycle=3600,   # Recycle connections after 1 hour
    connect_args={
        "server_settings": {
            "application_name": "notetaker_service",
        },
        "command_timeout": 10,
        "timeout": 10,
    }
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def init_db():
    """Initialize database and create tables"""
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
        print("Database tables created/verified")
    except Exception as e:
        print(f"Database initialization failed: {e}")
        raise  # Re-raise so caller knows it failed

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI endpoints"""
    async with async_session_factory() as session:
        yield session
