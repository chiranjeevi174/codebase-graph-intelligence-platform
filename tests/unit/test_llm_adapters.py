"""Unit tests for LLM message converters in app/llm/adapters.py."""

import pytest

from app.llm.adapters import to_groq_messages, to_openai_messages


def test_to_openai_messages_valid_roles():
    raw_messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain graph RAG."},
        {"role": "assistant", "content": "Graph RAG integrates Neo4j with LLMs."},
        {"role": "developer", "content": "Internal instructions."},
        {"role": "tool", "content": "Tool output", "tool_call_id": "call_123"},
    ]
    converted = to_openai_messages(raw_messages)
    assert len(converted) == 5
    assert converted[0] == {"role": "system", "content": "You are a helpful assistant."}
    assert converted[1] == {"role": "user", "content": "Explain graph RAG."}
    assert converted[2] == {"role": "assistant", "content": "Graph RAG integrates Neo4j with LLMs."}
    assert converted[3] == {"role": "developer", "content": "Internal instructions."}
    assert converted[4] == {"role": "tool", "content": "Tool output", "tool_call_id": "call_123"}


def test_to_openai_messages_unsupported_role():
    raw_messages = [{"role": "unsupported_role", "content": "test"}]
    with pytest.raises(ValueError, match="Unsupported message role for OpenAI provider"):
        to_openai_messages(raw_messages)


def test_to_groq_messages_valid_roles():
    raw_messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "User prompt"},
        {"role": "assistant", "content": "Assistant prompt"},
        {"role": "tool", "content": "Tool result", "tool_call_id": "call_456"},
    ]
    converted = to_groq_messages(raw_messages)
    assert len(converted) == 4
    assert converted[0] == {"role": "system", "content": "System prompt"}
    assert converted[1] == {"role": "user", "content": "User prompt"}
    assert converted[2] == {"role": "assistant", "content": "Assistant prompt"}
    assert converted[3] == {"role": "tool", "content": "Tool result", "tool_call_id": "call_456"}


def test_to_groq_messages_unsupported_role():
    raw_messages = [{"role": "developer", "content": "test"}]
    with pytest.raises(ValueError, match="Unsupported message role for Groq provider"):
        to_groq_messages(raw_messages)
