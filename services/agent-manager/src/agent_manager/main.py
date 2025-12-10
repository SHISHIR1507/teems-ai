from contextlib import asynccontextmanager
import sys
from pathlib import Path
from fastapi import FastAPI
from loguru import logger

# Dynamically locate shared libs for CORS helper
current_file = Path(__file__).resolve()
current_dir = current_file.parent
while current_dir != current_dir.parent:
    shared_libs_candidate = current_dir / "platform" / "shared_libs"
    if shared_libs_candidate.exists():
        shared_libs_dir = shared_libs_candidate
        break
    current_dir = current_dir.parent
else:
    shared_libs_dir = current_file.parent.parent.parent / "platform" / "shared_libs"

sys.path.insert(0, str(shared_libs_dir))
from pyshared import add_env_cors  # noqa: E402

from .config import get_settings
from .database import init_db
from .routers import agents_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup
    logger.info("Starting Agent Manager service...")
    try:
        await init_db()
        logger.info("Agent Manager service started successfully")
    except Exception as e:
        logger.error(f"Failed to start Agent Manager service: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Agent Manager service...")


# Create FastAPI app
app = FastAPI(
    title="Agent Manager API",
    description="API for managing agents/creators catalogue",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware (env-driven origins with localhost defaults)
add_env_cors(app)

# Include routers
app.include_router(agents_router)

# Health check endpoint
@app.get("/", tags=["health"])
async def health_check():
    return {"status": "healthy", "service": "agent-manager"}


@app.get("/health", tags=["health"])
async def detailed_health_check():
    return {
        "status": "healthy",
        "service": "agent-manager",
        "version": "1.0.0"
    }