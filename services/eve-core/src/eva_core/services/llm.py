from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import Settings


class LLMClient(ABC):
    @abstractmethod
    async def generate(self, messages: list[dict[str, str]], model: str) -> str:
        ...


class AIMLLLMClient(LLMClient):
    """LLM client that talks to AIML API via the OpenAI-compatible SDK."""

    def __init__(self, api_key: str, base_url: str):
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def generate(self, messages: list[dict[str, str]], model: str) -> str:
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,
        )
        return response.choices[0].message.content or ""


class LLMFactory:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.clients: dict[str, LLMClient] = {}

    def get_client(self, provider: str) -> LLMClient:
        if provider not in self.clients:
            if provider not in ("openai", "gemini"):
                raise ValueError(f"Unsupported LLM provider: {provider}")

            if not self.settings.aiml_api_key:
                raise ValueError("AIML_API_KEY is required for LLM provider via AIML API")

            # Both OpenAI and Gemini models are accessed via the AIML API using the same
            # OpenAI-compatible client; the `model` name selects the underlying model.
            self.clients[provider] = AIMLLLMClient(
                api_key=self.settings.aiml_api_key,
                base_url=self.settings.aiml_base_url,
            )

        return self.clients[provider]

