from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import Settings


class LLMClient(ABC):
    @abstractmethod
    async def generate(self, messages: list[dict[str, str]], model: str, temperature: float = 0.7) -> str:
        ...


class OpenAILLM(LLMClient):
    """LLM client that talks to OpenAI API."""

    def __init__(self, api_key: str, base_url: str):
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.api_key = api_key
        self.base_url = base_url

    async def generate(self, messages: list[dict[str, str]], model: str, temperature: float = 0.7) -> str:
        # Log which API is being used
        provider = "AIML" if "aimlapi" in self.base_url else "OpenAI"
        masked_key = f"{self.api_key[:8]}...{self.api_key[-4:]}" if len(self.api_key) > 12 else "***"
        print(f"[{provider} API] Using key: {masked_key} | Base URL: {self.base_url}")

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
            if not self.settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY is required for LLM provider")

            self._client = OpenAILLM(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url,
            )

        return self._client

    async def generate(
        self, messages: list[dict[str, str]], model: str | None = None, temperature: float = 0.7
    ) -> str:
        client = self.get_client()
        model_name = model or self.settings.default_llm_model
        return await client.generate(messages, model_name, temperature)

