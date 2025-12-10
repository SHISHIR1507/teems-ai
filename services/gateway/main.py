from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.routing import APIRouter
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
    shared_libs_dir = current_file.parent.parent.parent / "platform" / "shared_libs"

sys.path.insert(0, str(shared_libs_dir))
from pyshared import add_env_cors  # noqa: E402

from .auth import AuthenticatedUser, require_tenant
from .config import Settings, get_settings
from .rate_limit import rate_limit

router = APIRouter()


async def get_redis(settings: Settings = Depends(get_settings)) -> Optional[Redis]:
    if not settings.redis_url:
        return None
    return Redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)


async def get_http_client() -> httpx.AsyncClient:
    async with httpx.AsyncClient(timeout=20.0) as client:
        yield client


@router.post("/v1/chat")
async def chat_proxy(
    request: Request,
    user: AuthenticatedUser = Depends(require_tenant()),
    settings: Settings = Depends(get_settings),
    redis: Optional[Redis] = Depends(get_redis),
    client: httpx.AsyncClient = Depends(get_http_client),
) -> Any:
    await rate_limit(redis, key=f"chat:{user.tenant_id}", limit=settings.rate_limit_requests, window_seconds=settings.rate_limit_window_seconds)

    payload = await request.json()
    # Enforce server-side tenant/user identity
    payload["tenant_id"] = user.tenant_id
    payload.setdefault("metadata", {})
    payload["metadata"]["user_id"] = user.sub

    try:
        resp = await client.post(
            f"{settings.eve_core_base_url}/v1/rag/chat",
            json=payload,
            headers={"Authorization": request.headers.get("Authorization", "")},
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Eve Core unreachable: {exc}") from exc

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.post("/v1/ingest/text")
async def ingest_text_proxy(
    request: Request,
    user: AuthenticatedUser = Depends(require_tenant()),
    settings: Settings = Depends(get_settings),
    redis: Optional[Redis] = Depends(get_redis),
    client: httpx.AsyncClient = Depends(get_http_client),
) -> Any:
    await rate_limit(redis, key=f"ingest:{user.tenant_id}", limit=settings.rate_limit_requests, window_seconds=settings.rate_limit_window_seconds)

    payload = await request.json()
    payload["tenant_id"] = user.tenant_id
    payload.setdefault("metadata", {})
    payload["metadata"]["user_id"] = user.sub

    try:
        resp = await client.post(
            f"{settings.eve_core_base_url}/v1/rag/ingest/text",
            json=payload,
            headers={"Authorization": request.headers.get("Authorization", "")},
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Eve Core unreachable: {exc}") from exc

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.post("/v1/agent/{agent_id}/run")
async def run_agent(
    agent_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(require_tenant()),
    settings: Settings = Depends(get_settings),
    redis: Optional[Redis] = Depends(get_redis),
    client: httpx.AsyncClient = Depends(get_http_client),
) -> Any:
    await rate_limit(redis, key=f"agent_run:{user.tenant_id}", limit=settings.rate_limit_requests, window_seconds=settings.rate_limit_window_seconds)

    payload = await request.json()
    payload["tenant_id"] = user.tenant_id
    payload["user_id"] = user.sub

    try:
        resp = await client.post(
            f"{settings.agent_manager_base_url}/api/agents/{agent_id}/run",
            json=payload,
            headers={"Authorization": request.headers.get("Authorization", "")},
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Agent Manager unreachable: {exc}") from exc

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


def create_app() -> FastAPI:
    settings = get_settings()
    logger.info("Booting Gateway in {} mode", settings.env)

    app = FastAPI(
        title="Teems Gateway",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    add_env_cors(app)
    app.include_router(router)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.on_event("shutdown")
    async def shutdown_event() -> None:
        # Close any shared redis connections cleanly
        redis: Optional[Redis] = None
        try:
            redis = await get_redis(settings)
            if redis:
                await redis.close()
        except Exception:
            pass

    return app


app = create_app()


