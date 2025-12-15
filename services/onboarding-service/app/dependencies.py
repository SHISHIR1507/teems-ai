from fastapi import Depends
from redis.asyncio import ConnectionPool, Redis
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings, get_settings
from .database import get_session
from .events import EventPublisher
from .services.llm import LLMService
from .services.clients import BrandfetchClient

_settings = get_settings()
_redis_pool: ConnectionPool | None = None
_redis: Redis | None = None
_publisher: EventPublisher | None = None
_llm_service: LLMService | None = None
_brandfetch_client: BrandfetchClient | None = None


def get_settings_dep() -> Settings:
    return _settings


async def get_redis_dep() -> Redis | None:
    global _redis_pool, _redis
    if _redis is not None:
        return _redis
    if not _settings.redis_url:
        return None
    # Create connection pool for high concurrency
    if _redis_pool is None:
        _redis_pool = ConnectionPool.from_url(
            _settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,  # Max connections in pool
        )
    _redis = Redis(connection_pool=_redis_pool)
    return _redis


async def get_publisher_dep(redis: Redis | None = Depends(get_redis_dep)) -> EventPublisher:
    global _publisher
    if _publisher is None:
        _publisher = EventPublisher(redis)
    return _publisher


def get_llm_service_dep(settings: Settings = Depends(get_settings_dep)) -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService(settings)
    return _llm_service


def get_brandfetch_client_dep(settings: Settings = Depends(get_settings_dep)) -> BrandfetchClient:
    global _brandfetch_client
    if _brandfetch_client is None:
        _brandfetch_client = BrandfetchClient(settings)
    return _brandfetch_client
