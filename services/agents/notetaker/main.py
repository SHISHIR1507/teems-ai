import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Dynamically locate shared libs for CORS helper
current_file = Path(__file__).resolve()
current_dir = current_file.parent

# First check Docker location: /app/shared_libs (when platform/shared_libs is copied to /app/shared_libs)
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
        # Fallback: go to repo root from services/agents/notetaker/ directory
        shared_libs_dir = current_file.parent.parent.parent.parent / "platform" / "shared_libs"

if shared_libs_dir and shared_libs_dir.exists():
    sys.path.insert(0, str(shared_libs_dir))
    try:
        from pyshared import add_env_cors  # noqa: E402
    except ImportError:
        # Fallback to basic CORS if shared libs not available
        from fastapi.middleware.cors import CORSMiddleware
        def add_env_cors(app):
            app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
else:
    # No shared libs found, use fallback
    from fastapi.middleware.cors import CORSMiddleware
    def add_env_cors(app):
        app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

from app.core.database import init_db
from app.routers import meetings, webhooks, health

app = FastAPI(title="Notetaker Service")

# Add CORS middleware (env-driven origins with localhost defaults)
add_env_cors(app)

# Initialize database (with error handling)
@app.on_event("startup")
async def startup_event():
    try:
        await init_db()
    except Exception as e:
        print(f"⚠️ Database initialization warning: {e}")
        print("Service will start but database operations may fail until database is available")

# Include routers
app.include_router(meetings.router, tags=["meetings"])
app.include_router(webhooks.router, tags=["webhooks"])
app.include_router(health.router, tags=["health"])

# Static files (only mount if directory exists)
frontend_dir = Path("../frontend")
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="static")
