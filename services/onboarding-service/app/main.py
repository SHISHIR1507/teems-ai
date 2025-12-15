from fastapi import FastAPI
from loguru import logger
import sys
from pathlib import Path

# Get paths - dynamically find repo root by looking for platform/shared_libs
current_file = Path(__file__).resolve()  # services/onboarding-service/app/main.py
current_dir = current_file.parent
# Traverse up until we find platform/shared_libs
while current_dir != current_dir.parent:  # Stop at filesystem root
    shared_libs_candidate = current_dir / "platform" / "shared_libs"
    if shared_libs_candidate.exists():
        shared_libs_dir = shared_libs_candidate
        break
    current_dir = current_dir.parent
else:
    # Fallback: assume we're 5 levels deep from root
    shared_libs_dir = current_file.parent.parent.parent.parent.parent / "platform" / "shared_libs"

# Add shared_libs directory to Python path
sys.path.insert(0, str(shared_libs_dir))

try:
    # Now this should work (pyshared is in shared_libs directory)
    from pyshared import add_env_cors
    print(f"Imported pyshared from {shared_libs_dir}")
except ImportError as e:
    print(f"Failed to import pyshared: {e}")
    print("Using fallback CORS...")
    
    # Fallback implementation matching pyshared behavior
    def add_env_cors(app):
        import os
        from fastapi.middleware.cors import CORSMiddleware
        
        # Parse CORS_ALLOWED_ORIGINS from env
        env_origins_str = os.getenv("CORS_ALLOWED_ORIGINS", "")
        env_origins = [o.strip() for o in env_origins_str.split(",") if o.strip()] if env_origins_str else []
        
        # Default localhost origins
        default_origins = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
        
        # Merge and deduplicate
        all_origins = list(dict.fromkeys(default_origins + env_origins))
        
        app.add_middleware(
            CORSMiddleware,
            allow_origins=all_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

from .config import get_settings
from .database import init_models
from .routers import chat_router, health_router


def create_app() -> FastAPI:
    settings = get_settings()
    logger.info("Starting Onboarding Service in {} mode", settings.env)

    app = FastAPI(
        title="Onboarding Service",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Apply CORS using env-driven configuration plus localhost defaults.
    add_env_cors(app)

    @app.on_event("startup")
    async def on_startup() -> None:
        await init_models()
        logger.info("Database tables ensured for Onboarding Service")

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        """Cleanup connections on shutdown."""
        from .dependencies import _brandfetch_client, _redis
        if _brandfetch_client:
            await _brandfetch_client.close()
        if _redis:
            await _redis.close()
        logger.info("Onboarding Service shutdown complete")

    app.include_router(health_router)
    app.include_router(chat_router)

    return app


app = create_app()

