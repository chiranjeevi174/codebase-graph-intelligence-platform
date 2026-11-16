"""Unit tests for LLM provider abstraction and factory."""

from unittest.mock import AsyncMock, MagicMock, patch

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
    assert provider.model_name == "gpt-6-luna"


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
    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["max_tokens"] == 4096
    assert kwargs["temperature"] == 0.2


@pytest.mark.anyio
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


@patch("app.llm.openai_provider.OpenAI")
def test_openai_provider_reasoning_model(mock_openai_cls):
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Reasoning response"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai_cls.return_value = mock_client

    provider = OpenAIProvider(api_key="sk-test", model="o3-mini")
    result = provider.generate("Hello o3", max_tokens=2048)

    assert result == "Reasoning response"
    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["max_completion_tokens"] == 2048
    assert "max_tokens" not in kwargs
    assert "temperature" not in kwargs


@patch("app.llm.openai_provider.OpenAI")
def test_openai_provider_temperature_and_max_tokens_sequential_fallback(mock_openai_cls):
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Multi-fallback response"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    err1 = Exception(
        "Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead."
    )
    err2 = Exception(
        "Unsupported value: 'temperature' does not support 0.2 with this model. Only the default (1) value is supported."
    )
    mock_client.chat.completions.create.side_effect = [err1, err2, mock_response]
    mock_openai_cls.return_value = mock_client

    # Use custom model name that isn't statically classified as a reasoning model
    provider = OpenAIProvider(api_key="sk-test", model="my-custom-model")
    result = provider.generate("Hello custom", temperature=0.2, max_tokens=1024)

    assert result == "Multi-fallback response"
    assert mock_client.chat.completions.create.call_count == 3

    final_kwargs = mock_client.chat.completions.create.call_args_list[2].kwargs
    assert final_kwargs["max_completion_tokens"] == 1024
    assert "max_tokens" not in final_kwargs
    assert "temperature" not in final_kwargs


def test_extract_response_content_formats():
    """Verify extract_response_content handles string, structured list, refusal, and fallback."""
    from app.llm.openai_provider import extract_response_content

    # 1. Plain string content
    choice_str = MagicMock()
    choice_str.message.content = "Simple answer"
    choice_str.message.refusal = None
    choice_str.finish_reason = "stop"
    text, _, meta = extract_response_content(choice_str)
    assert text == "Simple answer"
    assert meta["finish_reason"] == "stop"

    # 2. Multipart list with dict blocks
    choice_list_dict = MagicMock()
    choice_list_dict.message.content = [
        {"type": "text", "text": "Part 1. "},
        {"type": "text", "text": "Part 2."},
    ]
    choice_list_dict.message.refusal = None
    choice_list_dict.finish_reason = "stop"
    text, _, _ = extract_response_content(choice_list_dict)
    assert text == "Part 1. Part 2."

    # 3. Multipart list with object blocks (.text)
    block1 = MagicMock()
    block1.text = "Hello "
    block2 = MagicMock()
    block2.text = "World!"
    choice_list_obj = MagicMock()
    choice_list_obj.message.content = [block1, block2]
    choice_list_obj.message.refusal = None
    choice_list_obj.finish_reason = "stop"
    text, _, _ = extract_response_content(choice_list_obj)
    assert text == "Hello World!"

    # 4. Refusal content
    choice_refusal = MagicMock()
    choice_refusal.message.content = None
    choice_refusal.message.refusal = "Safety policy violation"
    choice_refusal.finish_reason = "stop"
    text, _, _ = extract_response_content(choice_refusal)
    assert text == "Safety policy violation"

    # 5. Reasoning content fallback when content is empty
    choice_reasoning = MagicMock()
    choice_reasoning.message.content = ""
    choice_reasoning.message.refusal = None
    choice_reasoning.message.reasoning_content = "Internal reasoning explanation"
    choice_reasoning.finish_reason = "length"
    text, _, meta = extract_response_content(choice_reasoning)
    assert text == "Internal reasoning explanation"
    assert meta["finish_reason"] == "length"


@patch("app.llm.openai_provider.OpenAI")
def test_openai_provider_token_starvation_retry(mock_openai_cls):
    """Verify that when finish_reason=='length' and content is empty, provider retries with boosted tokens."""
    mock_client = MagicMock()

    # Attempt 0: token starvation (length finish, empty content)
    choice_starved = MagicMock()
    choice_starved.message.content = ""
    choice_starved.message.refusal = None
    del choice_starved.message.reasoning_content
    choice_starved.finish_reason = "length"
    resp_starved = MagicMock()
    resp_starved.choices = [choice_starved]

    # Attempt 1: succeeds with content
    choice_ok = MagicMock()
    choice_ok.message.content = "Full answer generated after token boost"
    choice_ok.message.refusal = None
    choice_ok.finish_reason = "stop"
    resp_ok = MagicMock()
    resp_ok.choices = [choice_ok]

    mock_client.chat.completions.create.side_effect = [resp_starved, resp_ok]
    mock_openai_cls.return_value = mock_client

    provider = OpenAIProvider(api_key="sk-test", model="gpt-6-luna")
    result = provider.generate("Complex reasoning query", max_tokens=1024)

    assert result == "Full answer generated after token boost"
    assert mock_client.chat.completions.create.call_count == 2
    second_call_kwargs = mock_client.chat.completions.create.call_args_list[1].kwargs
    assert second_call_kwargs["max_completion_tokens"] >= 4096


@patch("app.llm.openai_provider.OpenAI")
def test_openai_provider_empty_response_raises_error(mock_openai_cls):
    """Verify that if LLM returns empty content after all attempts, LLMProviderError is raised."""
    mock_client = MagicMock()
    choice_empty = MagicMock()
    choice_empty.message.content = ""
    choice_empty.message.refusal = None
    del choice_empty.message.reasoning_content
    choice_empty.finish_reason = "stop"
    resp_empty = MagicMock()
    resp_empty.choices = [choice_empty]

    mock_client.chat.completions.create.return_value = resp_empty
    mock_openai_cls.return_value = mock_client

    provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")
    with pytest.raises(LLMProviderError, match="returned empty text content"):
        provider.generate("Test prompt")
