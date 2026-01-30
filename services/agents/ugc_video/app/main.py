"""
FastAPI application entry point
"""
# Fix for Python 3.13 asyncio event loop issue on Windows
import sys
if sys.platform == 'win32':
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
import os
from pathlib import Path

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
        # Fallback: go to repo root from app/ directory (match agent-manager pattern)
        shared_libs_dir = current_file.parent.parent.parent / "platform" / "shared_libs"

if shared_libs_dir and shared_libs_dir.exists():
    sys.path.insert(0, str(shared_libs_dir))
    try:
        from pyshared import add_env_cors  # noqa: E402
    except ImportError:
        # Fallback: parse CORS_ALLOWED_ORIGINS from env with safe defaults
        from fastapi.middleware.cors import CORSMiddleware
        from app.core.config import get_cors_origins
        
        def add_env_cors(app):
            app.add_middleware(
                CORSMiddleware,
                allow_origins=get_cors_origins(),
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"]
            )
else:
    # Fallback: parse CORS_ALLOWED_ORIGINS from env with safe defaults
    from fastapi.middleware.cors import CORSMiddleware
    from app.core.config import get_cors_origins
    
    def add_env_cors(app):
        app.add_middleware(
            CORSMiddleware,
            allow_origins=get_cors_origins(),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"]
        )

from app.core.database import init_db
from app.api.routes import brand_sync, ugc, conversation, health, avatars

app = FastAPI(
    title="UGC Orchestrator API with DB & S3",
    description="CrewAI-based agent service for UGC video generation with tenant isolation",
    version="2.0.0"
)

# Add CORS middleware (no wildcards, specific origins only)
add_env_cors(app)

# Include routers with versioned paths
app.include_router(health.router, tags=["health"])
app.include_router(brand_sync.router, tags=["brand-sync"])
app.include_router(ugc.router, tags=["ugc"])
app.include_router(conversation.router, tags=["conversations"])
app.include_router(avatars.router, tags=["avatars"])


@app.on_event("startup")
async def startup_event():
    """Initialize database tables on startup"""
    try:
        await init_db()
        print("✅ Server started with database & S3 integration")
    except Exception as e:
        print(f"⚠️  Database initialization failed: {e}")
        print("⚠️  API will start but database operations may fail")


@app.get("/")
async def serve_frontend():
    """Serve the chatbox HTML frontend"""
    if os.path.exists("chatbox.html"):
        return FileResponse("chatbox.html")
    return {"message": "Frontend not found"}


@app.get("/image/{filename}", deprecated=True)
async def get_image(filename: str):
    """
    [DEPRECATED] Retrieve a generated image by filename (legacy - for local files only)
    
    This endpoint is deprecated and should not be used for new flows.
    Reason: Only works for local files, breaks in containers and multi-instance deployments.
    
    For new implementations:
    - Use S3 URLs directly from the database
    - Or generate presigned URLs for client access
    """
    if not os.path.exists(filename):
        raise HTTPException(status_code=404, detail="Image not found")
    
    return FileResponse(filename, media_type="image/png")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
