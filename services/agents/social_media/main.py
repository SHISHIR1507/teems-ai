"""
TikTok Posting Service
FastAPI application with SQLAlchemy async ORM
"""

import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Dynamically locate shared libs for CORS helper (if available)
current_file = Path(__file__).resolve()
current_dir = current_file.parent

# First check Docker location: /app/shared_libs
docker_shared_libs = current_file.parent.parent.parent / "shared_libs"
if docker_shared_libs.exists():
    shared_libs_dir = docker_shared_libs
else:
    # Otherwise, traverse up to find platform/shared_libs (local development)
    while current_dir != current_dir.parent:
        shared_libs_candidate = current_dir / "platform" / "shared_libs"
        if shared_libs_candidate.exists():
            shared_libs_dir = shared_libs_candidate
            break
        current_dir = current_dir.parent
    else:
        # Fallback: go to repo root
        shared_libs_dir = current_file.parent.parent.parent.parent / "platform" / "shared_libs"

if shared_libs_dir and shared_libs_dir.exists():
    sys.path.insert(0, str(shared_libs_dir))
    try:
        from pyshared import add_env_cors
    except ImportError:
        from fastapi.middleware.cors import CORSMiddleware
        def add_env_cors(app):
            app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
else:
    from fastapi.middleware.cors import CORSMiddleware
    def add_env_cors(app):
        app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

from app.core.database import init_db
from app.routers import health, chat, tiktok, oauth


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    try:
        await init_db()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"⚠️  Database initialization failed: {e}")
        print("⚠️  API will start but database operations may fail")
        print("⚠️  Check your DATABASE_URL and network connectivity")
    
    yield
    # Shutdown (if needed)


app = FastAPI(
    title="TikTok Posting Service",
    description="Simple API for posting videos to TikTok with AI chat interface",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
add_env_cors(app)

# Create static directory if it doesn't exist
os.makedirs("static", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(chat.router, tags=["chat"])
app.include_router(tiktok.router, tags=["tiktok"])
app.include_router(oauth.router, tags=["oauth"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
