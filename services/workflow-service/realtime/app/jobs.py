from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import WebSocket


@dataclass(slots=True)
class JobRecord:
    id: str
    owner: str
    status: str = "pending"
    payload: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class JobManager:
    """In-memory job registry suitable for lightweight realtime demos."""

    def __init__(self, default_duration: float = 3.0) -> None:
        self.default_duration = default_duration
        self.connections: dict[str, WebSocket] = {}
        self.jobs: dict[str, JobRecord] = {}
        self._lock = asyncio.Lock()

    async def register(self, websocket: WebSocket) -> str:
        connection_id = uuid4().hex
        async with self._lock:
            self.connections[connection_id] = websocket
        return connection_id

    async def connection_count(self) -> int:
        async with self._lock:
            return len(self.connections)

    async def unregister(self, connection_id: str) -> None:
        async with self._lock:
            self.connections.pop(connection_id, None)

    async def create_job(self, connection_id: str, payload: dict[str, Any]) -> JobRecord:
        job_id = uuid4().hex
        record = JobRecord(id=job_id, owner=connection_id, payload=payload)
        async with self._lock:
            self.jobs[job_id] = record

        duration = float(payload.get("duration") or self.default_duration)
        asyncio.create_task(self._simulate_job(record, duration))
        return record

    async def _simulate_job(self, record: JobRecord, duration: float) -> None:
        try:
            await asyncio.sleep(max(duration, 0))
            record.result = {"echo": record.payload.get("data"), "duration": duration}
            record.status = "completed"
        except Exception as exc:  # pragma: no cover - defensive logging
            record.error = str(exc)
            record.status = "failed"
        finally:
            record.updated_at = datetime.now(timezone.utc)
            await self._notify_owner(record)

    async def _notify_owner(self, record: JobRecord) -> None:
        websocket = self.connections.get(record.owner)
        if websocket is None:
            return
        message = {
            "type": "JOB_COMPLETED" if record.status == "completed" else "JOB_ERROR",
            "job_id": record.id,
            "status": record.status,
            "result": record.result,
            "error": record.error,
        }
        try:
            await websocket.send_json(message)
        except Exception:
            # Swallow send errors; the REST endpoint remains available.
            pass

    async def get_job(self, job_id: str) -> JobRecord | None:
        async with self._lock:
            return self.jobs.get(job_id)

