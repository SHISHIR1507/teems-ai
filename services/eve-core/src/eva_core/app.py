from fastapi import FastAPI
from loguru import logger

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

    @app.on_event("startup")
    async def _startup() -> None:
        await init_db()
        logger.info("Database initialized with pgvector support")

    app.include_router(router)
    return app

