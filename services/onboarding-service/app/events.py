from __future__ import annotations

import json
from typing import Any, Optional

from redis.asyncio import Redis


class EventPublisher:
    """Lightweight Redis pubsub helper for onboarding events."""

    def __init__(self, redis: Optional[Redis]) -> None:
        self.redis = redis

    async def publish(self, channel: str, payload: dict[str, Any]) -> None:
        if not self.redis:
            return
        await self.redis.publish(channel, json.dumps(payload))

