from fastapi import FastAPI
from loguru import logger
import sys
from pathlib import Path

# Get paths - dynamically find repo root by looking for platform/shared_libs
current_file = Path(__file__).resolve()  # services/eve-core/src/eva_core/app.py
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


from .api.routes import router
from .config import get_settings
from .database.session import init_db, init_engine


def create_app() -> FastAPI:
    settings = get_settings()
    logger.info("Starting Eve Core in {} mode", settings.env)
    init_engine(settings)

    app = FastAPI(
        title="Eve Core RAG Service",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Apply CORS using env-driven configuration plus localhost defaults.
    add_env_cors(app)

    @app.on_event("startup")
    async def _startup() -> None:
        try:
            await init_db()
            logger.info("Database initialized with pgvector support")
        except Exception as e:
            logger.error("Application startup failed due to database connection error: {}", str(e))
            logger.error(
                "Please verify your DATABASE_URL environment variable and ensure the database server is running and accessible."
            )
            raise

    app.include_router(router)
    return app

