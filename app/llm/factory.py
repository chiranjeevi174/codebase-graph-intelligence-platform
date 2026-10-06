"""LLM Provider Factory for obtaining provider instances dynamically."""

from typing import ClassVar

from app.config.settings import Settings, get_settings
from app.llm.base import BaseLLMProvider
from app.llm.openai_provider import OpenAIProvider
from app.utils.exceptions import LLMProviderError
from app.utils.logger import logger


class LLMFactory:
    """Factory for instantiating provider-agnostic LLM clients."""

    _providers: ClassVar[dict[str, type[BaseLLMProvider]]] = {
        "openai": OpenAIProvider,
    }

    @classmethod
    def register_provider(cls, name: str, provider_cls: type[BaseLLMProvider]):
        """Register a new custom LLM provider class."""
        cls._providers[name.lower()] = provider_cls

    @classmethod
    def get_llm(cls, provider: str | None = None, settings: Settings | None = None) -> BaseLLMProvider:
        """Instantiate and return configured LLM provider.

        Args:
            provider: Optional provider name ("openai"). If None, uses settings.LLM_PROVIDER.
            settings: Optional Settings object.

        Returns:
            Instance of BaseLLMProvider.
        """
        cfg = settings or get_settings()
        target_provider = (provider or cfg.LLM_PROVIDER).lower()

        provider_cls = cls._providers.get(target_provider)
        if not provider_cls:
            raise LLMProviderError(
                f"Unsupported LLM provider '{target_provider}'. Available providers: {list(cls._providers.keys())}"
            )

        logger.info(f"Instantiating LLM provider '{target_provider}'...")
        return provider_cls(settings=cfg)


def get_llm(provider: str | None = None) -> BaseLLMProvider:
    """Convenience module function to get LLM provider instance."""
    return LLMFactory.get_llm(provider=provider)
