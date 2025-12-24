from fastapi import Depends
from redis.asyncio import Redis

from .config import Settings, get_settings
from .events import EventPublisher
from .services.llm import LLMService

_settings = get_settings()
_redis: Redis | None = None
_publisher: EventPublisher | None = None
_llm_service: LLMService | None = None


def get_settings_dep() -> Settings:
    return _settings


async def get_redis_dep() -> Redis | None:
    global _redis
    if _redis is not None:
        return _redis
    if not _settings.redis_url:
        return None
    _redis = Redis.from_url(_settings.redis_url, encoding="utf-8", decode_responses=True)
    return _redis


async def get_publisher_dep(redis: Redis | None = Depends(get_redis_dep)) -> EventPublisher:
    global _publisher
    if _publisher is None:
        _publisher = EventPublisher(redis)
    return _publisher


def get_llm_service() -> LLMService | None:
    global _llm_service
    if _llm_service is None:
        if not _settings.aiml_api_key:
            return None
        _llm_service = LLMService(_settings)
    return _llm_service


