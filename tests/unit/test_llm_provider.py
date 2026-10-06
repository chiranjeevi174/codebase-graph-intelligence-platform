"""Unit tests for LLM provider abstraction and factory."""

from unittest.mock import MagicMock, AsyncMock, patch
import pytest

from app.config.settings import Settings
from app.llm.base import BaseLLMProvider
from app.llm.factory import LLMFactory
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
    settings = Settings(LLM_PROVIDER="openai", OPENAI_API_KEY="test_key")
    provider = LLMFactory.get_llm(settings=settings)
    assert isinstance(provider, OpenAIProvider)
    assert provider.provider_name == "openai"


def test_llm_factory_openai_provider():
    settings = Settings(LLM_PROVIDER="openai", OPENAI_API_KEY="test_key")
    provider = LLMFactory.get_llm(provider="openai", settings=settings)
    assert isinstance(provider, OpenAIProvider)
    assert provider.provider_name == "openai"
    assert provider.model_name == "gpt-4o-mini"


def test_llm_factory_custom_registration():
    LLMFactory.register_provider("mock", MockLLMProvider)
    provider = LLMFactory.get_llm(provider="mock")
    assert provider.provider_name == "mock"
    assert provider.generate("What is AST?") == "Mock answer to: What is AST?"


def test_llm_provider_missing_key_error():
    openai_provider = OpenAIProvider(api_key="")
    with pytest.raises(LLMProviderError):
        openai_provider.generate("Test prompt")


@patch("app.llm.openai_provider.OpenAI")
def test_openai_provider_generate(mock_openai_cls):
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Response text"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai_cls.return_value = mock_client

    provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")
    result = provider.generate("Hello", system_prompt="System instructions")

    assert result == "Response text"
    mock_client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
@patch("app.llm.openai_provider.AsyncOpenAI")
async def test_openai_provider_agenerate(mock_async_openai_cls):
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Async response text"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    mock_async_openai_cls.return_value = mock_client

    provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")
    result = await provider.agenerate("Hello async", system_prompt="System instructions")

    assert result == "Async response text"
    mock_client.chat.completions.create.assert_called_once()


