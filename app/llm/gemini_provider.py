"""Google Gemini LLM Provider implementation."""


from google import genai
from google.genai import types

from app.config.settings import Settings, get_settings
from app.llm.base import BaseLLMProvider
from app.utils.exceptions import LLMProviderError


class GeminiProvider(BaseLLMProvider):
    """LLM Provider wrapping Google Gemini API via google-genai SDK."""

    def __init__(self, api_key: str | None = None, model: str | None = None, settings: Settings | None = None):
        super().__init__(settings=settings)
        self.settings = settings or get_settings()
        self.api_key = api_key or self.settings.GEMINI_API_KEY
        self._model = model or self.settings.GEMINI_MODEL
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if not self.api_key:
            raise LLMProviderError("GEMINI_API_KEY is not configured in environment variables or settings.")
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        client = self._get_client()
        config = types.GenerateContentConfig(
            system_instruction=system_prompt if system_prompt else None,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        try:
            response = client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=config,
            )
            return response.text or ""
        except Exception as e:
            raise LLMProviderError(f"Gemini generation error: {e}")

    async def agenerate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        client = self._get_client()
        config = types.GenerateContentConfig(
            system_instruction=system_prompt if system_prompt else None,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        try:
            response = await client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=config,
            )
            return response.text or ""
        except Exception as e:
            raise LLMProviderError(f"Gemini async generation error: {e}")

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model
