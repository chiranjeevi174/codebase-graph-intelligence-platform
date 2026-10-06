"""Abstract Base Class for LLM Providers."""

from abc import ABC, abstractmethod
from typing import Any


class BaseLLMProvider(ABC):
    """Provider-agnostic interface for LLM text generation."""

    def __init__(self, settings: Any = None, **kwargs):
        """Initialize provider with optional settings and configuration."""
        self.settings = settings


    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        """Synchronously generate text response from LLM provider."""

    @abstractmethod
    async def agenerate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        """Asynchronously generate text response from LLM provider."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider identifier name (e.g. openai)."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return configured model identifier."""
