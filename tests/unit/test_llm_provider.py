"""Unit tests for LLM provider abstraction and factory."""

import pytest

from app.config.settings import Settings
from app.llm.base import BaseLLMProvider
from app.llm.factory import LLMFactory
from app.llm.gemini_provider import GeminiProvider
from app.llm.groq_provider import GroqProvider
from app.llm.openai_provider import OpenAIProvider
from app.utils.exceptions import LLMProviderError


class MockLLMProvider(BaseLLMProvider):
    def __init__(self, settings=None):
        self.settings = settings

    def generate(self, prompt: str, system_prompt=None, temperature=0.2, max_tokens=1024) -> str:
        return f"Mock answer to: {prompt}"

    async def agenerate(self, prompt: str, system_prompt=None, temperature=0.2, max_tokens=1024) -> str:
        return f"Async Mock answer to: {prompt}"

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-v1"


def test_llm_factory_default_provider():
    settings = Settings(LLM_PROVIDER="groq", GROQ_API_KEY="test_key")
    provider = LLMFactory.get_llm(settings=settings)
    assert isinstance(provider, GroqProvider)
    assert provider.provider_name == "groq"


def test_llm_factory_gemini_provider():
    settings = Settings(LLM_PROVIDER="gemini", GEMINI_API_KEY="test_key")
    provider = LLMFactory.get_llm(provider="gemini", settings=settings)
    assert isinstance(provider, GeminiProvider)
    assert provider.provider_name == "gemini"


def test_llm_factory_openai_provider():
    settings = Settings(LLM_PROVIDER="openai", OPENAI_API_KEY="test_key")
    provider = LLMFactory.get_llm(provider="openai", settings=settings)
    assert isinstance(provider, OpenAIProvider)
    assert provider.provider_name == "openai"


def test_llm_factory_custom_registration():
    LLMFactory.register_provider("mock", MockLLMProvider)
    provider = LLMFactory.get_llm(provider="mock")
    assert provider.provider_name == "mock"
    assert provider.generate("What is AST?") == "Mock answer to: What is AST?"


def test_llm_provider_missing_key_error():
    groq_provider = GroqProvider(api_key="")
    with pytest.raises(LLMProviderError):
        groq_provider.generate("Test prompt")


def test_llm_factory_provider_without_custom_init():
    class DefaultInitProvider(BaseLLMProvider):
        def generate(self, prompt: str, system_prompt=None, temperature=0.2, max_tokens=1024) -> str:
            return "ok"
        async def agenerate(self, prompt: str, system_prompt=None, temperature=0.2, max_tokens=1024) -> str:
            return "ok"
        @property
        def provider_name(self) -> str:
            return "default_init"
        @property
        def model_name(self) -> str:
            return "default-v1"

    LLMFactory.register_provider("default_init", DefaultInitProvider)
    provider = LLMFactory.get_llm(provider="default_init")
    assert provider.provider_name == "default_init"

