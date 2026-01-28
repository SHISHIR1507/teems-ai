"""
FastAPI application entry point
"""
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI

current_file = Path(__file__).resolve()
current_dir = current_file.parent

docker_shared_libs = current_file.parent.parent.parent / "shared_libs"
if docker_shared_libs.exists():
    shared_libs_dir = docker_shared_libs
else:
    shared_libs_dir = None
    while current_dir != current_dir.parent:
        candidate = current_dir / "platform" / "shared_libs"
        if candidate.exists():
            shared_libs_dir = candidate
            break
        current_dir = current_dir.parent
    if shared_libs_dir is None:
        shared_libs_dir = current_file.parent.parent.parent.parent / "platform" / "shared_libs"

if shared_libs_dir and shared_libs_dir.exists():
    sys.path.insert(0, str(shared_libs_dir))
    try:
        from pyshared import add_env_cors
    except ImportError:
        from fastapi.middleware.cors import CORSMiddleware
        def add_env_cors(app):
            default_origins = [
                "http://localhost:3000", "http://127.0.0.1:3000",
                "http://localhost:5173", "http://127.0.0.1:5173",
                "http://localhost:8000",
                "https://teems-web-app.vercel.app", "http://teems-web-app.vercel.app",
                "https://dev.teems.ai", "https://teems.ai",
            ]
            env_origins_str = os.getenv("CORS_ALLOWED_ORIGINS", "")
            env_origins = []
            if env_origins_str:
                for part in env_origins_str.split(","):
                    env_origins.extend(part.split())
                env_origins = [o.strip() for o in env_origins if o.strip()]
            all_origins = []
            seen = set()
            for o in default_origins + env_origins:
                if o not in seen:
                    seen.add(o)
                    all_origins.append(o)
            app.add_middleware(
                CORSMiddleware,
                allow_origins=all_origins,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
else:
    from fastapi.middleware.cors import CORSMiddleware
    def add_env_cors(app):
        default_origins = [
            "http://localhost:3000", "http://127.0.0.1:3000",
            "http://localhost:5173", "http://127.0.0.1:5173",
            "http://localhost:8000",
            "https://teems-web-app.vercel.app", "http://teems-web-app.vercel.app",
            "https://dev.teems.ai", "https://teems.ai",
        ]
        env_origins_str = os.getenv("CORS_ALLOWED_ORIGINS", "")
        env_origins = []
        if env_origins_str:
            for part in env_origins_str.split(","):
                env_origins.extend(part.split())
            env_origins = [o.strip() for o in env_origins if o.strip()]
        all_origins = []
        seen = set()
        for o in default_origins + env_origins:
            if o not in seen:
                seen.add(o)
                all_origins.append(o)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=all_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

from app.core.database import init_db
from app.api.routes import (
    health,
    chat,
    conversations,
    posts,
    tokens,
    oauth,
    tiktok,
    facebook,
    upload,
)


from app.services.scheduler_service import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
        print("✅ Server started with database & Auth0 integration")
    except Exception as e:
        print(f"⚠️  Database initialization failed: {e}")
        print("⚠️  API will start but database operations may fail")
    
    # Start background scheduler for scheduled posts
    try:
        start_scheduler()
        print("✅ Background scheduler started for scheduled posts")
    except Exception as e:
        print(f"⚠️  Scheduler initialization failed: {e}")
        print("⚠️  Scheduled posting will not work until scheduler is available")
    
    yield
    
    # Stop scheduler on shutdown
    try:
        stop_scheduler()
        print("✅ Background scheduler stopped")
    except Exception as e:
        print(f"⚠️  Error stopping scheduler: {e}")


app = FastAPI(
    title="Social Media Agent API",
    description="CrewAI-based agent for multi-platform social media posting (TikTok, Facebook)",
    version="1.0.0",
    lifespan=lifespan,
)

add_env_cors(app)

app.include_router(health.router, tags=["health"])
app.include_router(chat.router, tags=["chat"])
app.include_router(conversations.router, tags=["conversations"])
app.include_router(posts.router, tags=["posts"])
app.include_router(tokens.router, tags=["tokens"])
app.include_router(oauth.router, tags=["oauth"])
app.include_router(tiktok.router, tags=["tiktok"])
app.include_router(facebook.router, tags=["facebook"])
app.include_router(upload.router, tags=["upload"])
