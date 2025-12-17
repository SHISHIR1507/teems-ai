from fastapi import Depends

from .config import Settings, get_settings
from .database.session import get_session
from redis.asyncio import Redis
from .services.embedding import EmbeddingProvider, get_embedding_provider
from .services.llm import LLMFactory
from .events import EventPublisher
from .services.message_service import MessageService
from .services.query_rewriter import QueryRewriterService
from sqlalchemy.ext.asyncio import AsyncSession


_settings = get_settings()
_embedder = get_embedding_provider(_settings)
_llm_factory = LLMFactory(_settings)
_redis: Redis | None = None
_publisher: EventPublisher | None = None


def get_settings_dep() -> Settings:
    return _settings


def get_embedding_dep() -> EmbeddingProvider:
    return _embedder


def get_llm_factory_dep() -> LLMFactory:
    return _llm_factory


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

async def get_message_service_dep(
    session: AsyncSession = Depends(get_session),
) -> MessageService:
    return MessageService(session)

async def get_query_rewriter_dep(
    message_service: MessageService = Depends(get_message_service_dep),
) -> QueryRewriterService:
    return QueryRewriterService(message_service)
