from __future__ import annotations

import time
from typing import Optional

from fastapi import HTTPException, status
from redis.asyncio import Redis


async def rate_limit(
    redis: Optional[Redis],
    key: str,
    *,
    limit: int,
    window_seconds: int,
) -> None:
    """
    Simple sliding-window-ish counter using Redis INCR+EXPIRE.
    If Redis is not configured, rate limiting is skipped.
    """
    if redis is None:
        return

    now = int(time.time())
    window_key = f"rl:{key}:{now // window_seconds}"

    async with redis.pipeline() as pipe:
        pipe.incr(window_key)
        pipe.expire(window_key, window_seconds)
        count, _ = await pipe.execute()

    if int(count) > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please retry shortly.",
        )


