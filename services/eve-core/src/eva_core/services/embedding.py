from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Iterable

from ..config import Settings


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...

    async def embed_one(self, text: str) -> list[float]:
        return (await self.embed([text]))[0]


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, api_key: str, model: str):
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self.client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]


class GeminiEmbeddingProvider(EmbeddingProvider):
    def __init__(self, api_key: str, model: str):
        import google.generativeai as genai

        self.genai = genai
        self.genai.configure(api_key=api_key)
        self.model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        async def _embed(text: str) -> list[float]:
            def blocking_call() -> list[float]:
                result = self.genai.embed_content(model=self.model, content=text)
                return result["embedding"]

            return await asyncio.to_thread(blocking_call)

        return [await _embed(text) for text in texts]


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI embeddings")
        return OpenAIEmbeddingProvider(settings.openai_api_key, settings.embedding_model)

    if settings.embedding_provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required for Gemini embeddings")
        return GeminiEmbeddingProvider(settings.gemini_api_key, settings.embedding_model)

    raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")

