from __future__ import annotations

import io
from typing import Any

from fastapi import FastAPI, File, UploadFile
from loguru import logger
import sys
from pathlib import Path

from .config import get_settings

# Locate shared libs for CORS helper
current_file = Path(__file__).resolve()
current_dir = current_file.parent
while current_dir != current_dir.parent:
    shared_libs_candidate = current_dir / "platform" / "shared_libs"
    if shared_libs_candidate.exists():
        shared_libs_dir = shared_libs_candidate
        break
    current_dir = current_dir.parent
else:
    shared_libs_dir = current_file.parent.parent.parent / "platform" / "shared_libs"

sys.path.insert(0, str(shared_libs_dir))
from pyshared import add_env_cors  # noqa: E402


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="Parsers Service", version="0.1.0", docs_url="/docs", redoc_url="/redoc")

    add_env_cors(app)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/parse", tags=["parse"])
    async def parse(file: UploadFile = File(...)) -> Any:
        content = await file.read()
        text = content.decode(errors="ignore")
        logger.info("Parsed file {}", file.filename)
        return {
            "text": text,
            "tables": [],
            "images": [],
            "artifacts": [],
        }

    return app


app = create_app()


