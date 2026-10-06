"""Type-safe adapters for converting internal message representations to provider SDK message params."""

from typing import Any

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
