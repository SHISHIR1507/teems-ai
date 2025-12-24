from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import Settings


class LLMClient(ABC):
    @abstractmethod
    async def generate(self, messages: list[dict[str, str]], model: str, temperature: float = 0.7) -> str:
        ...


class AIMLLLMClient(LLMClient):
    """LLM client that talks to AIML API via the OpenAI-compatible SDK."""

    def __init__(self, api_key: str, base_url: str):
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def generate(self, messages: list[dict[str, str]], model: str, temperature: float = 0.7) -> str:
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""


class LLMService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: LLMClient | None = None

    def get_client(self) -> LLMClient:
        if self._client is None:
            if not self.settings.aiml_api_key:
                raise ValueError("AIML_API_KEY is required for LLM provider via AIML API")

            self._client = AIMLLLMClient(
                api_key=self.settings.aiml_api_key,
                base_url=self.settings.aiml_base_url,
            )

        return self._client

    async def generate(
        self, messages: list[dict[str, str]], model: str | None = None, temperature: float = 0.7
    ) -> str:
        client = self.get_client()
        model_name = model or self.settings.default_llm_model
        return await client.generate(messages, model_name, temperature)

