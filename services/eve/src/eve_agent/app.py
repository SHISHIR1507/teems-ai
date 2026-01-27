from fastapi import FastAPI
from loguru import logger
import sys
from pathlib import Path

from .core.config import get_settings
from .core.database import init_db
from .api.routes import router
from .dependencies import initialize_mcp_clients

settings = get_settings()

def _add_env_cors(app: FastAPI) -> None:
    """
    Apply env-driven CORS (same pattern as eve-core).
    Tries to import `pyshared.add_env_cors` from platform/shared_libs; falls back to safe defaults.
    """
    current_file = Path(__file__).resolve()  # services/eve/src/eve_agent/app.py (in repo) or /app/src/eve_agent/app.py (in container)
    current_dir = current_file.parent

    # Traverse up until we find platform/shared_libs
    while current_dir != current_dir.parent:
        shared_libs_candidate = current_dir / "platform" / "shared_libs"
        if shared_libs_candidate.exists():
            shared_libs_dir = shared_libs_candidate
            break
        current_dir = current_dir.parent
    else:
        # Fallback: assume we're 3 levels deep from service root
        shared_libs_dir = current_file.parent.parent.parent / "platform" / "shared_libs"

    sys.path.insert(0, str(shared_libs_dir))

    try:
        from pyshared import add_env_cors  # type: ignore
    except ImportError as e:
        logger.warning("Failed to import pyshared.add_env_cors: {}. Using fallback CORS.", str(e))
        from fastapi.middleware.cors import CORSMiddleware

        def add_env_cors(app: FastAPI) -> None:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=[
                    "http://localhost:3000",
                    "http://127.0.0.1:3000",
                    "http://localhost:5173",
                    "http://127.0.0.1:5173",
                    "http://localhost:8000",
                    "https://teems-web-app.vercel.app",
                ],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

    add_env_cors(app)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    logger.info("Starting Eve Agent in {} mode", settings.env)
    
    app = FastAPI(
        title="Eve AI Server",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Apply env-driven CORS plus localhost defaults (no wildcard)
    _add_env_cors(app)

    @app.on_event("startup")
    async def startup_event():
        """Initialize MCP clients and database on startup"""
        logger.info("🚀 Starting Eve Web Server...")
        logger.info("=" * 50)
        
        # Initialize database
        try:
            import asyncio
            asyncio.run(init_db())
            logger.info("Database initialized")
        except Exception as e:
            logger.warning(f"Database initialization warning: {e}")
        
        # Initialize MCP clients
        initialize_mcp_clients()
        logger.info("\n🌐 Server ready")

    app.include_router(router)
    return app
