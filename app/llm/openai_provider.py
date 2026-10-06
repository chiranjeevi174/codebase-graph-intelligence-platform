"""OpenAI LLM Provider implementation."""

from typing import Any

from openai import AsyncOpenAI, OpenAI, OpenAIError

from app.config.settings import Settings, get_settings
from app.llm.adapters import to_openai_messages
from app.llm.base import BaseLLMProvider
from app.utils.exceptions import LLMProviderError


class OpenAIProvider(BaseLLMProvider):
    """LLM Provider wrapping OpenAI API."""

    def __init__(self, api_key: str | None = None, model: str | None = None, settings: Settings | None = None):
        super().__init__(settings=settings)
        self.settings = settings or get_settings()
        self.api_key = self.settings.OPENAI_API_KEY if api_key is None else api_key
        self._model = model or self.settings.OPENAI_MODEL
        self._client: OpenAI | None = None
        self._async_client: AsyncOpenAI | None = None

    def _get_client(self) -> OpenAI:
        if not self.api_key:
            raise LLMProviderError("OPENAI_API_KEY is not configured in environment variables or settings.")
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def _get_async_client(self) -> AsyncOpenAI:
        if not self.api_key:
            raise LLMProviderError("OPENAI_API_KEY is not configured in environment variables or settings.")
        if self._async_client is None:
            self._async_client = AsyncOpenAI(api_key=self.api_key)
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
        messages = to_openai_messages(raw_messages)

        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except (OpenAIError, Exception) as e:  # noqa: BLE001
            raise LLMProviderError(f"OpenAI generation error: {e}")

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
        messages = to_openai_messages(raw_messages)

        try:
            response = await client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except (OpenAIError, Exception) as e:  # noqa: BLE001
            raise LLMProviderError(f"OpenAI async generation error: {e}")

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model
