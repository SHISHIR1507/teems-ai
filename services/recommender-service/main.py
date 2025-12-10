from __future__ import annotations

from typing import Any

from fastapi import FastAPI
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
    app = FastAPI(title="Recommender Service", version="0.1.0", docs_url="/docs", redoc_url="/redoc")

    add_env_cors(app)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/recommend", tags=["recommend"])
    async def recommend(payload: dict[str, Any]) -> dict[str, Any]:
        # Simple deterministic chips for now
        chips = [
            {"label": "Summarize", "action": "summarize"},
            {"label": "Create Agent", "action": "create_agent"},
            {"label": "Upgrade plan", "action": "upgrade"},
        ]
        return {"chips": chips}

    return app


app = create_app()


