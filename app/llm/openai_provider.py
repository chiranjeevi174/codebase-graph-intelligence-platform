"""OpenAI LLM Provider implementation."""

from typing import Any

from openai import AsyncOpenAI, OpenAI, OpenAIError

from app.config.settings import Settings, get_settings
from app.llm.adapters import to_openai_messages
from app.llm.base import BaseLLMProvider
from app.utils.exceptions import LLMProviderError
from app.utils.logger import logger


def extract_response_content(choice: Any) -> tuple[str, str | None, dict[str, Any]]:
    """Safely extract response content, handling str, list, refusal, and AIMessage structures."""
    message = getattr(choice, "message", choice)
    content = getattr(message, "content", None)
    refusal = getattr(message, "refusal", None)
    finish_reason = getattr(choice, "finish_reason", None)

    text = ""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            elif hasattr(item, "text"):
                parts.append(str(item.text))
        text = "".join(parts)
    elif content is not None:
        text = str(content)

    # Fallback to refusal if content is empty
    if not text.strip() and refusal:
        text = str(refusal)

    # Fallback to reasoning_content if content is empty
    if not text.strip() and hasattr(message, "reasoning_content") and message.reasoning_content:
        text = str(message.reasoning_content)

    metadata = {
        "finish_reason": finish_reason,
        "content_type": type(content).__name__,
        "has_refusal": bool(refusal),
        "content_length": len(text),
    }
    return text, refusal, metadata


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

    def _is_reasoning_model(self) -> bool:
        model_lower = self._model.lower()
        reasoning_indicators = ("o1", "o3", "o4", "gpt-5", "gpt-6", "luna", "deepseek-r", "reasoning")
        return any(ind in model_lower for ind in reasoning_indicators)

    def _prepare_kwargs(
        self, prompt: str, system_prompt: str | None, temperature: float, max_tokens: int
    ) -> dict[str, Any]:
        raw_messages: list[dict[str, Any]] = []
        if system_prompt:
            raw_messages.append({"role": "system", "content": system_prompt})
        raw_messages.append({"role": "user", "content": prompt})
        messages = to_openai_messages(raw_messages)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }

        if self._is_reasoning_model():
            # Reasoning models use max_completion_tokens and do not support custom temperature
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["temperature"] = temperature
            kwargs["max_tokens"] = max_tokens

        return kwargs

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        client = self._get_client()
        kwargs = self._prepare_kwargs(prompt, system_prompt, temperature, max_tokens)

        for attempt in range(3):
            try:
                response = client.chat.completions.create(**kwargs)
                choice = response.choices[0]
                text, _refusal, meta = extract_response_content(choice)

                logger.info(
                    f"[OpenAIProvider] Invocation succeeded (model='{self._model}', attempt={attempt}, "
                    f"finish_reason='{meta['finish_reason']}', content_len={meta['content_length']})."
                )

                # If token limit was hit with empty content, boost completion tokens and retry
                if meta["finish_reason"] == "length" and not text.strip() and attempt < 2:
                    current_budget = kwargs.get("max_completion_tokens", max_tokens)
                    boosted = max(current_budget * 2, 4096)
                    logger.warning(
                        f"[OpenAIProvider] Model ran out of tokens before emitting visible text. "
                        f"Boosting budget from {current_budget} to {boosted} and retrying."
                    )
                    kwargs.pop("max_tokens", None)
                    kwargs["max_completion_tokens"] = boosted
                    continue

                if not text.strip():
                    raise LLMProviderError(
                        f"OpenAI model '{self._model}' returned empty text content (finish_reason='{meta['finish_reason']}')."
                    )

                return text
            except (OpenAIError, Exception) as err:
                err_msg = str(err).lower()
                modified = False
                if "max_tokens" in kwargs and ("max_tokens" in err_msg or "max_completion_tokens" in err_msg):
                    kwargs.pop("max_tokens", None)
                    kwargs["max_completion_tokens"] = max_tokens
                    modified = True
                if "temperature" in kwargs and "temperature" in err_msg:
                    kwargs.pop("temperature", None)
                    modified = True

                if not modified or attempt == 2:
                    raise LLMProviderError(f"OpenAI generation error: {err}") from err

        raise LLMProviderError("OpenAI generation failed after parameter adjustments.")

    async def agenerate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        client = self._get_async_client()
        kwargs = self._prepare_kwargs(prompt, system_prompt, temperature, max_tokens)

        for attempt in range(3):
            try:
                response = await client.chat.completions.create(**kwargs)
                choice = response.choices[0]
                text, _refusal, meta = extract_response_content(choice)

                logger.info(
                    f"[OpenAIProvider] Async invocation succeeded (model='{self._model}', attempt={attempt}, "
                    f"finish_reason='{meta['finish_reason']}', content_len={meta['content_length']})."
                )

                if meta["finish_reason"] == "length" and not text.strip() and attempt < 2:
                    current_budget = kwargs.get("max_completion_tokens", max_tokens)
                    boosted = max(current_budget * 2, 4096)
                    kwargs.pop("max_tokens", None)
                    kwargs["max_completion_tokens"] = boosted
                    continue

                if not text.strip():
                    raise LLMProviderError(
                        f"OpenAI model '{self._model}' returned empty text content (finish_reason='{meta['finish_reason']}')."
                    )

                return text
            except (OpenAIError, Exception) as err:
                err_msg = str(err).lower()
                modified = False
                if "max_tokens" in kwargs and ("max_tokens" in err_msg or "max_completion_tokens" in err_msg):
                    kwargs.pop("max_tokens", None)
                    kwargs["max_completion_tokens"] = max_tokens
                    modified = True
                if "temperature" in kwargs and "temperature" in err_msg:
                    kwargs.pop("temperature", None)
                    modified = True

                if not modified or attempt == 2:
                    raise LLMProviderError(f"OpenAI async generation error: {err}") from err

        raise LLMProviderError("OpenAI async generation failed after parameter adjustments.")

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model
