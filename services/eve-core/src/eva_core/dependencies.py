from fastapi import Depends

from .config import Settings, get_settings
from .database.session import get_session
from .services.embedding import EmbeddingProvider, get_embedding_provider
from .services.llm import LLMFactory

_settings = get_settings()
_embedder = get_embedding_provider(_settings)
_llm_factory = LLMFactory(_settings)


def get_settings_dep() -> Settings:
    return _settings


def get_embedding_dep() -> EmbeddingProvider:
    return _embedder


def get_llm_factory_dep() -> LLMFactory:
    return _llm_factory

