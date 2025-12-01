from fastapi import FastAPI
from loguru import logger

from pyshared import add_env_cors
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

