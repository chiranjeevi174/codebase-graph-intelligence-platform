"""Groq LLM Provider implementation."""


from typing import Any

from groq import AsyncGroq, Groq

from app.config.settings import Settings, get_settings
from app.llm.adapters import to_groq_messages
from app.llm.base import BaseLLMProvider
from app.utils.exceptions import LLMProviderError


class GroqProvider(BaseLLMProvider):
    """LLM Provider wrapping Groq API."""

    def __init__(self, api_key: str | None = None, model: str | None = None, settings: Settings | None = None):
        super().__init__(settings=settings)
        self.settings = settings or get_settings()
        self.api_key = self.settings.GROQ_API_KEY if api_key is None else api_key
        self._model = model or self.settings.GROQ_MODEL
        self._client: Groq | None = None
        self._async_client: AsyncGroq | None = None

    def _get_client(self) -> Groq:
        if not self.api_key:
            raise LLMProviderError("GROQ_API_KEY is not configured in environment variables or settings.")
        if self._client is None:
            self._client = Groq(api_key=self.api_key)
        return self._client

    def _get_async_client(self) -> AsyncGroq:
        if not self.api_key:
            raise LLMProviderError("GROQ_API_KEY is not configured in environment variables or settings.")
        if self._async_client is None:
            self._async_client = AsyncGroq(api_key=self.api_key)
        return self._async_client

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        client = self._get_client()
        raw_messages: list[dict[str, Any]] = []
        if system_prompt:
            raw_messages.append({"role": "system", "content": system_prompt})
        raw_messages.append({"role": "user", "content": prompt})
        messages = to_groq_messages(raw_messages)

        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            raise LLMProviderError(f"Groq generation error: {e}")

    async def agenerate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        client = self._get_async_client()
        raw_messages: list[dict[str, Any]] = []
        if system_prompt:
            raw_messages.append({"role": "system", "content": system_prompt})
        raw_messages.append({"role": "user", "content": prompt})
        messages = to_groq_messages(raw_messages)

        try:
            response = await client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            raise LLMProviderError(f"Groq async generation error: {e}")

    @property
    def provider_name(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return self._model
