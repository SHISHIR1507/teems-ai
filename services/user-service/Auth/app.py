from fastapi import FastAPI
from loguru import logger

from pyshared import add_env_cors
from .config import get_settings
from .routers import auth_router, health_router


def create_app() -> FastAPI:
    """Instantiate FastAPI application and register routers."""
    settings = get_settings()
    logger.info("Bootstrapping Auth service with domain {}", settings.auth0_domain)

    app = FastAPI(
        title="Teems User Service",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Apply CORS using env-driven configuration plus localhost defaults.
    # Env var (optional): CORS_ALLOWED_ORIGINS="https://app.example.com, https://admin.example.com"
    add_env_cors(app)

    app.include_router(health_router)
    app.include_router(auth_router)

    return app

