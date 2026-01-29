from __future__ import annotations

from abc import ABC, abstractmethod

from ...core.config import get_settings

settings = get_settings()


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...

    async def embed_one(self, text: str) -> list[float]:
        return (await self.embed([text]))[0]


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Embedding provider that uses OpenAI API directly."""

    def __init__(self, api_key: str, base_url: str, model: str):
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self.client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]


def get_embedding_provider(settings) -> EmbeddingProvider:
    """
    Factory for embeddings via OpenAI API.

    The model string (`EMBEDDING_MODEL`) determines which embedding model to use.
    Default is `text-embedding-3-small`.
    """
    if settings.embedding_provider not in ("openai", "gemini"):
        raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")

    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required for embeddings")

    return OpenAIEmbeddingProvider(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.embedding_model,
    )

