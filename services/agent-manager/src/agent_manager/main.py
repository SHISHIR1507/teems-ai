from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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