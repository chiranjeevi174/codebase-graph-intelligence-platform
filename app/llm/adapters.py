"""Type-safe adapters for converting internal message representations to provider SDK message params."""

from typing import Any

from groq.types.chat import (
    ChatCompletionAssistantMessageParam as GroqAssistantMessageParam,
    ChatCompletionMessageParam as GroqMessageParam,
    ChatCompletionSystemMessageParam as GroqSystemMessageParam,
    ChatCompletionToolMessageParam as GroqToolMessageParam,
    ChatCompletionUserMessageParam as GroqUserMessageParam,
)
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionDeveloperMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionToolMessageParam,
    ChatCompletionUserMessageParam,
)


def to_openai_messages(messages: list[dict[str, Any]]) -> list[ChatCompletionMessageParam]:
    """Convert raw dictionary messages to OpenAI ChatCompletionMessageParam objects."""
    typed_messages: list[ChatCompletionMessageParam] = []
    for msg in messages:
        role = msg.get("role")
        content = str(msg.get("content", ""))
        if role == "system":
            sys_msg: ChatCompletionSystemMessageParam = {"role": "system", "content": content}
            typed_messages.append(sys_msg)
        elif role == "user":
            user_msg: ChatCompletionUserMessageParam = {"role": "user", "content": content}
            typed_messages.append(user_msg)
        elif role == "assistant":
            asst_msg: ChatCompletionAssistantMessageParam = {"role": "assistant", "content": content}
            typed_messages.append(asst_msg)
        elif role == "developer":
            dev_msg: ChatCompletionDeveloperMessageParam = {"role": "developer", "content": content}
            typed_messages.append(dev_msg)
        elif role == "tool":
            tool_call_id = str(msg.get("tool_call_id", ""))
            tool_msg: ChatCompletionToolMessageParam = {
                "role": "tool",
                "content": content,
                "tool_call_id": tool_call_id,
            }
            typed_messages.append(tool_msg)
        else:
            raise ValueError(f"Unsupported message role for OpenAI provider: '{role}'")
    return typed_messages


def to_groq_messages(messages: list[dict[str, Any]]) -> list[GroqMessageParam]:
    """Convert raw dictionary messages to Groq ChatCompletionMessageParam objects."""
    typed_messages: list[GroqMessageParam] = []
    for msg in messages:
        role = msg.get("role")
        content = str(msg.get("content", ""))
        if role == "system":
            groq_sys_msg: GroqSystemMessageParam = {"role": "system", "content": content}
            typed_messages.append(groq_sys_msg)
        elif role == "user":
            groq_user_msg: GroqUserMessageParam = {"role": "user", "content": content}
            typed_messages.append(groq_user_msg)
        elif role == "assistant":
            groq_asst_msg: GroqAssistantMessageParam = {"role": "assistant", "content": content}
            typed_messages.append(groq_asst_msg)
        elif role == "tool":
            tool_call_id = str(msg.get("tool_call_id", ""))
            groq_tool_msg: GroqToolMessageParam = {
                "role": "tool",
                "content": content,
                "tool_call_id": tool_call_id,
            }
            typed_messages.append(groq_tool_msg)
        else:
            raise ValueError(f"Unsupported message role for Groq provider: '{role}'")
    return typed_messages
