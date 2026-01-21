from __future__ import annotations

from abc import ABC, abstractmethod

from ...config import get_settings

settings = get_settings()


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...

    async def embed_one(self, text: str) -> list[float]:
        return (await self.embed([text]))[0]


class AIMLEmbeddingProvider(EmbeddingProvider):
    """Embedding provider that talks to AIML API via the OpenAI-compatible SDK."""

    def __init__(self, api_key: str, base_url: str, model: str):
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self.client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]


def get_embedding_provider(settings) -> EmbeddingProvider:
    """
    Factory for embeddings via AIML API.

    We keep `EMBEDDING_PROVIDER` (`openai` or `gemini`) for configuration symmetry,
    but both paths use the AIML API key and base URL. The actual model string
    (`EMBEDDING_MODEL`) determines which underlying model you hit (OpenAI, Gemini, etc.)
    as documented in the AIML API docs: `https://docs.aimlapi.com/quickstart/setting-up`.
    """
    if settings.embedding_provider not in ("openai", "gemini"):
        raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")

    if not settings.aiml_api_key:
        raise ValueError("AIML_API_KEY is required for embeddings via AIML API")

    return AIMLEmbeddingProvider(
        api_key=settings.aiml_api_key,
        base_url=settings.aiml_base_url,
        model=settings.embedding_model,
    )
