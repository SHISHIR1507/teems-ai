"""
FastAPI application entry point
"""
from fastapi import FastAPI
import os
import sys
from pathlib import Path

# Dynamically locate shared libs for CORS helper
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
        # Fallback: parse CORS_ALLOWED_ORIGINS from env with safe defaults
        from fastapi.middleware.cors import CORSMiddleware
        def add_env_cors(app):
            # Safe default origins for local development
            default_origins = [
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:8000",
                "https://teems-web-app.vercel.app",
                "http://teems-web-app.vercel.app",
            ]
            
            # Parse CORS_ALLOWED_ORIGINS from environment
            env_origins_str = os.getenv("CORS_ALLOWED_ORIGINS", "")
            env_origins = []
            if env_origins_str:
                # Support both comma and space separated lists
                for part in env_origins_str.split(","):
                    env_origins.extend(part.split())
                env_origins = [origin.strip() for origin in env_origins if origin.strip()]
            
            # Merge defaults with env origins, preserving order and de-duplicating
            all_origins = []
            seen = set()
            for origin in default_origins + env_origins:
                if origin not in seen:
                    seen.add(origin)
                    all_origins.append(origin)
            
            app.add_middleware(
                CORSMiddleware,
                allow_origins=all_origins,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"]
            )
else:
    # Fallback: parse CORS_ALLOWED_ORIGINS from env with safe defaults
    from fastapi.middleware.cors import CORSMiddleware
    def add_env_cors(app):
        # Safe default origins for local development
        default_origins = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "https://teems-web-app.vercel.app",
            "http://teems-web-app.vercel.app",
        ]
        
        # Parse CORS_ALLOWED_ORIGINS from environment
        env_origins_str = os.getenv("CORS_ALLOWED_ORIGINS", "")
        env_origins = []
        if env_origins_str:
            # Support both comma and space separated lists
            for part in env_origins_str.split(","):
                env_origins.extend(part.split())
            env_origins = [origin.strip() for origin in env_origins if origin.strip()]
        
        # Merge defaults with env origins, preserving order and de-duplicating
        all_origins = []
        seen = set()
        for origin in default_origins + env_origins:
            if origin not in seen:
                seen.add(origin)
                all_origins.append(origin)
        
        app.add_middleware(
            CORSMiddleware,
            allow_origins=all_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"]
        )

from app.core.database import init_db
from app.api.routes import (
    health,
    chat,
    presentations,
    upload,
    webhooks,
    templates,
    tasks,
    conversations
)

app = FastAPI(
    title="Presentation Agent API",
    description="CrewAI-based agent for SlideSpeak API integration",
    version="1.0.0"
)

# Add CORS middleware
add_env_cors(app)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(chat.router, tags=["chat"])
app.include_router(presentations.router, tags=["presentations"])
app.include_router(upload.router, tags=["upload"])
app.include_router(webhooks.router, tags=["webhooks"])
app.include_router(templates.router, tags=["templates", "brand"])
app.include_router(tasks.router, tags=["tasks"])
app.include_router(conversations.router, tags=["conversations"])


@app.on_event("startup")
async def startup_event():
    """Initialize database tables on startup"""
    try:
        await init_db()
        print("✅ Server started with database & S3 integration")
    except Exception as e:
        print(f"⚠️  Database initialization failed: {e}")
        print("⚠️  API will start but database operations may fail")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    from app.services.realtime_notifier import close_redis
    await close_redis()
    print("✅ Shutdown complete")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
