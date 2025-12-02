from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from loguru import logger

import sys
from pathlib import Path

# Get paths - dynamically find repo root by looking for platform/shared_libs
current_file = Path(__file__).resolve()  # services/workflow-service/realtime/app/main.py
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

from .config import Settings, get_settings
from .jobs import JobManager


def create_app() -> FastAPI:
    settings = get_settings()
    logger.info("Booting realtime workflow service in {} mode", settings.env)

    app = FastAPI(
        title="Realtime Workflow Service",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Apply CORS using env-driven configuration plus localhost defaults.
    # Note: browsers don't use CORS for WebSocket upgrade itself, but this
    # is important for any HTTP endpoints the frontend calls.
    add_env_cors(app)

    job_manager = JobManager(default_duration=settings.default_job_duration_seconds)

    @app.on_event("startup")
    async def startup_event() -> None:
        logger.info("Realtime service ready; allowing up to {} sockets", settings.max_connections)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/jobs/{job_id}", tags=["jobs"])
    async def get_job(job_id: str) -> Any:
        job = await job_manager.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return {
            "job_id": job.id,
            "status": job.status,
            "result": job.result,
            "error": job.error,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
        }

    @app.websocket("/ws")
    async def websocket_handler(websocket: WebSocket, settings: Settings = Depends(get_settings)) -> None:
        if await job_manager.connection_count() >= settings.max_connections:
            await websocket.close(code=1013, reason="Too many clients connected")
            return

        await websocket.accept()
        connection_id = await job_manager.register(websocket)
        logger.debug("WebSocket {} connected", connection_id)

        try:
            await websocket.send_json({"type": "WELCOME", "connection_id": connection_id})
            while True:
                message = await websocket.receive_json()
                action = message.get("action")

                if action == "ping":
                    await websocket.send_json({"type": "PONG"})
                    continue

                if action != "create_job":
                    await websocket.send_json(
                        {
                            "type": "ERROR",
                            "error": "Unsupported action. Use 'create_job'.",
                        }
                    )
                    continue

                payload = message.get("payload") or {}
                job = await job_manager.create_job(connection_id, payload)
                await websocket.send_json(
                    {
                        "type": "JOB_ACCEPTED",
                        "job_id": job.id,
                        "status": job.status,
                    }
                )

        except WebSocketDisconnect:
            logger.debug("WebSocket {} disconnected", connection_id)
        except Exception as exc:  # pragma: no cover
            logger.exception("WebSocket {} crashed: {}", connection_id, exc)
            await websocket.close(code=1011)
        finally:
            await job_manager.unregister(connection_id)

    return app


app = create_app()

