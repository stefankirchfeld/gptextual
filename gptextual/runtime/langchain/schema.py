from datetime import datetime
from typing import List
from langchain_core.messages import (
    BaseMessage,
    FunctionMessage,
    ToolMessage,
    AIMessage,
    AIMessageChunk,
)
from pydantic import BaseModel, Json


class Function(BaseModel):
    arguments: Json
    name: str


class ToolCall(BaseModel):
    id: str
    function: Function
    type: str


class ToolCalls(BaseModel):
    calls: List[ToolCall]


def new_message_of_type(type: BaseMessage, *, content: str = "", **kwargs):
    return type(
        content=content,
        additional_kwargs={
            "timestamp": datetime.utcnow().timestamp(),
            **kwargs,
        },
    )


def is_function_or_tool_call(message: BaseMessage):
    if isinstance(message, AIMessageChunk):
        return len(message.tool_call_chunks) > 0
    if isinstance(message, AIMessage):
        return len(message.tool_calls) > 0

    return False
    # return len(m.tool_calls)
    # return (
    #     message.additional_kwargs.get("tool_calls", None) is not None
    #     or message.additional_kwargs.get("function_call", None) is not None
    # )


def is_tool_related_message(message: BaseMessage):
    return isinstance(
        message, (FunctionMessage, ToolMessage)
    ) or is_function_or_tool_call(message)
