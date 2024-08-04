from __future__ import annotations

import pkg_resources
import json
from asyncio import iscoroutine

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool

from langchain_core.messages import AIMessage, ToolMessage

from gptextual.config.app_config import AppConfig, APIProviderConfig
from gptextual.runtime.models import ChatModel
from gptextual.logging import logger

# Central repository for registered functions
_FUNCTIONS_BY_NAME = {}
_LANGCHAIN_TOOLS_BY_NAME = {}


def load_function_entry_points():
    for entry_point in pkg_resources.iter_entry_points("gptextual_function"):
        # Just loading the entry point is enough if each function
        # is decorated with @register_for_function_calling below
        entry_point.load()


def bind_tools(model: ChatModel):
    app_config = AppConfig.get_instance()
    llm_model: BaseChatModel = model.llm_model
    provider_config: APIProviderConfig = getattr(
        app_config.api_config, model.api_provider, None
    )
    if not provider_config or (
        model.name not in provider_config.function_calling
        and "*" not in provider_config.function_calling
    ):
        return llm_model

    function_names = [
        name
        for name in _FUNCTIONS_BY_NAME.keys()
        if app_config.functions and name in app_config.functions
    ]
    tools = [_LANGCHAIN_TOOLS_BY_NAME.get(name, None) for name in function_names]
    tools = [t for t in tools if t is not None]
    if tools:
        try:
            return llm_model.bind_tools(tools)
        except NotImplementedError:
            logger().warn(
                f"Model {llm_model} does not support tool binding. Falling back without bound"
            )
    return llm_model


async def invoke_tools(message: AIMessage):
    results = []
    for tool_call in message.tool_calls:
        fname = tool_call["name"].lower()
        func = get_function(fname)
        if func is not None:
            try:
                if isinstance(tool_call["args"], str):
                    args = json.loads(tool_call["args"])
                else:
                    args = tool_call["args"]
                result = func(**args)
                if iscoroutine(result):
                    result = await result
                results.append(
                    ToolMessage(tool_call_id=tool_call["id"], content=str(result))
                )
            except Exception as ex:
                logger().error(
                    f"There was an error executing tool function {fname}: {ex}"
                )
                results.append(
                    ToolMessage(
                        tool_call_id=tool_call["id"],
                        content=f"There was an error executing tool function {fname}: {ex}. Try to fix the error or continue without it.",
                    )
                )
    return results


def get_function(function_name: str):
    return _FUNCTIONS_BY_NAME.get(function_name, None)


def register_for_function_calling(func):
    _FUNCTIONS_BY_NAME[func.__name__] = func
    _LANGCHAIN_TOOLS_BY_NAME[func.__name__] = tool(func)
    return func


def get_function_config(func):
    fname = func if isinstance(func, str) else func.__name__
    return AppConfig.get_instance().functions.get(fname, None)
