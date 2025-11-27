from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from ..config import Settings


class LLMClient(ABC):
    @abstractmethod
    async def generate(self, messages: list[dict[str, str]], model: str) -> str:
        ...


class OpenAILLMClient(LLMClient):
    def __init__(self, api_key: str):
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=api_key)

    async def generate(self, messages: list[dict[str, str]], model: str) -> str:
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,
        )
        return response.choices[0].message.content or ""


class GeminiLLMClient(LLMClient):
    def __init__(self, api_key: str):
        import google.generativeai as genai

        self.genai = genai
        self.genai.configure(api_key=api_key)

    async def generate(self, messages: list[dict[str, str]], model: str) -> str:
        def blocking_call() -> str:
            # Gemini expects a flat prompt. We'll concatenate messages.
            prompt_segments = []
            for message in messages:
                role = message["role"].upper()
                prompt_segments.append(f"{role}: {message['content']}")
            prompt = "\n".join(prompt_segments)

            llm = self.genai.GenerativeModel(model)
            response = llm.generate_content(prompt)
            return response.text or ""

        return await asyncio.to_thread(blocking_call)


class LLMFactory:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.clients: dict[str, LLMClient] = {}

    def get_client(self, provider: str) -> LLMClient:
        if provider not in self.clients:
            if provider == "openai":
                if not self.settings.openai_api_key:
                    raise ValueError("OPENAI_API_KEY is required for OpenAI provider")
                self.clients[provider] = OpenAILLMClient(self.settings.openai_api_key)
            elif provider == "gemini":
                if not self.settings.gemini_api_key:
                    raise ValueError("GEMINI_API_KEY is required for Gemini provider")
                self.clients[provider] = GeminiLLMClient(self.settings.gemini_api_key)
            else:
                raise ValueError(f"Unsupported LLM provider: {provider}")
        return self.clients[provider]

