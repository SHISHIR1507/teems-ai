from __future__ import annotations

import asyncio
import contextlib
import json
import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from loguru import logger
from redis.asyncio import Redis

current_file = Path(__file__).resolve()
current_dir = current_file.parent
while current_dir != current_dir.parent:
    shared_libs_candidate = current_dir / "platform" / "shared_libs"
    if shared_libs_candidate.exists():
        shared_libs_dir = shared_libs_candidate
        break
    current_dir = current_dir.parent
else:
    shared_libs_dir = current_file.parent.parent.parent.parent.parent / "platform" / "shared_libs"

sys.path.insert(0, str(shared_libs_dir))
try:
    from pyshared import add_env_cors
    print(f"Imported pyshared from {shared_libs_dir}")
except ImportError:
    from fastapi.middleware.cors import CORSMiddleware

    def add_env_cors(app):
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                "http://localhost:3000",
                "http://localhost:5173",
                "http://localhost:8000",
                "https://teems-web-app.vercel.app",
            ],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

from .auth import Auth0Client, AuthenticatedUser, authenticate_websocket, get_auth0_client
from .config import Settings, get_settings

redis_client: Optional[Redis] = None


async def get_redis(settings: Settings = Depends(get_settings)) -> Optional[Redis]:
    global redis_client
    if redis_client:
        return redis_client
    if not settings.redis_url:
        return None
    redis_client = Redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    return redis_client


async def pubsub_pump(pubsub, websocket: WebSocket):
    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            data = message["data"]
            payload = json.loads(data) if isinstance(data, str) else data
            await websocket.send_json(payload)
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to forward pubsub message: {}", exc)


def create_app() -> FastAPI:
    settings = get_settings()
    logger.info("Booting realtime workflow service in {} mode", settings.env)

    app = FastAPI(
        title="Realtime Workflow Service",
        version="0.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    add_env_cors(app)

    @app.on_event("shutdown")
    async def shutdown_event() -> None:
        global redis_client
        if redis_client:
            await redis_client.close()
            redis_client = None

    @app.get("/health", tags=["health"])
    async def health() -> Any:
        return JSONResponse({"status": "ok"})

    @app.websocket("/ws")
    async def websocket_handler(
        websocket: WebSocket,
        settings: Settings = Depends(get_settings),
        redis: Optional[Redis] = Depends(get_redis),
        auth0_client: Auth0Client = Depends(get_auth0_client),
    ) -> None:
        await websocket.accept()

        # First-message authentication
        user = await authenticate_websocket(
            websocket=websocket,
            client=auth0_client,
            timeout_seconds=10.0,
            require_tenant_id=True,
        )
        if user is None:
            # Socket already closed by authenticate_websocket
            return

        if redis is None:
            await websocket.send_json({"type": "ERROR", "error": "Redis not configured"})
            await websocket.close(code=1011)
            return

        pubsub = redis.pubsub()
        pump_task: asyncio.Task | None = None

        try:
            # Send welcome after auth success (user already got AUTH_SUCCESS)
            while True:
                message = await websocket.receive_json()
                action = message.get("action")

                if action == "ping":
                    await websocket.send_json({"type": "PONG"})
                    continue

                if action == "subscribe":
                    channels = message.get("channels") or []
                    channels = [ch for ch in channels if isinstance(ch, str)]
                    if not channels:
                        await websocket.send_json({"type": "ERROR", "error": "channels required"})
                        continue
                    await pubsub.subscribe(*channels)
                    if pump_task is None:
                        pump_task = asyncio.create_task(pubsub_pump(pubsub, websocket))
                    await websocket.send_json({"type": "SUBSCRIBED", "channels": channels})
                    continue

                await websocket.send_json({"type": "ERROR", "error": "Unsupported action"})

        except WebSocketDisconnect:
            logger.debug("WebSocket disconnected for user {}", user.sub)
        except Exception as exc:  # pragma: no cover
            logger.exception("WebSocket crashed: {}", exc)
            await websocket.close(code=1011)
        finally:
            if pump_task:
                pump_task.cancel()
                with contextlib.suppress(Exception):
                    await pump_task
            await pubsub.close()

    return app


app = create_app()
