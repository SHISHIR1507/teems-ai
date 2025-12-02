from fastapi import FastAPI
from loguru import logger
import sys
from pathlib import Path

# Get paths - dynamically find repo root by looking for platform/shared_libs
current_file = Path(__file__).resolve()  # services/workflow-service/BrandfetchAPI/app/main.py
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
    
    # Fallback implementation
    def add_env_cors(app):
        from fastapi.middleware.cors import CORSMiddleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:8000", "https://teems-web-app.vercel.app"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

from .config import get_settings
from .database import init_models
from .routers import brands_router, health_router


def create_app() -> FastAPI:
    settings = get_settings()
    logger.info("Starting BrandfetchAPI in {} mode", settings.env)

    app = FastAPI(
        title="Brandfetch Workflow Service",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Apply CORS using env-driven configuration plus localhost defaults.
    add_env_cors(app)

    @app.on_event("startup")
    async def on_startup() -> None:
        await init_models()
        logger.info("Database tables ensured for BrandfetchAPI")

    app.include_router(health_router)
    app.include_router(brands_router)

    return app


app = create_app()

