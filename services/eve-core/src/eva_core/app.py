from fastapi import FastAPI
from loguru import logger

from pyshared import add_env_cors
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

