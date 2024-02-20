from __future__ import annotations

import pkg_resources
from asyncio import iscoroutine
from enum import Enum
from functools import cache
from typing import List
from langchain_core.utils.function_calling import (
    convert_to_openai_function,
    convert_to_openai_tool,
)
from langchain_core.messages import AIMessage, FunctionMessage, ToolMessage

from gptextual.config.app_config import APIProviderConfig, AppConfig
from gptextual.logging import logger
from gptextual.runtime.langchain.schema import Function, ToolCalls

# Central repository for registered functions
_FUNCTIONS_BY_NAME = {}


class FunctionCallSupport(str, Enum):
    OPENAI_TOOL = "openai_tool"  # new parallel function calling API
    OPENAI_FUNCTION = "openai_function"  # old singular function call API

    @staticmethod
    def fromStr(name: str) -> FunctionCallSupport:
        if name == FunctionCallSupport.OPENAI_TOOL:
            return FunctionCallSupport.OPENAI_TOOL
        elif name == FunctionCallSupport.OPENAI_FUNCTION:
            return FunctionCallSupport.OPENAI_FUNCTION

        return None

    @staticmethod
    @cache
    def forModelName(*, model_name: str, api_provider: str):
        app_config = AppConfig.get_instance()
        function_support = _DEFAULT_FUNCTION_CALL_SUPPORT.get(api_provider, {})
        api_provider_config: APIProviderConfig = getattr(
            app_config.api_config, api_provider
        )
        if api_provider_config and api_provider_config.function_call_support:
            function_support = {
                **function_support,
                **api_provider_config.function_call_support,
            }

        # 1. Check if there are any tools registered for the current proxy type
        if function_support:
            support_by_model = {
                model_name.strip(): support
                for key, support in function_support.items()
                for model_name in key.split(",")
            }

            # 2. Check for use of wildcard (all models)
            if model_name not in support_by_model:
                model_name = "*"
            if model_name in support_by_model:
                return FunctionCallSupport.fromStr(support_by_model[model_name])

        return None

    async def execute_function_call(self, message: AIMessage):
        if self == FunctionCallSupport.OPENAI_FUNCTION:
            return await self._execute_openai_function(message)
        if self == FunctionCallSupport.OPENAI_TOOL:
            return await self._execute_openai_tool(message)

    async def _execute_openai_tool(self, message: AIMessage) -> List[ToolMessage]:
        tool_calls = message.additional_kwargs.get("tool_calls", None)
        if tool_calls:
            calls = ToolCalls(calls=tool_calls)
            results = []
            for call in calls.calls:
                fname = call.function.name
                func = get_function(fname)
                if func:
                    try:
                        result = func(**call.function.arguments)
                        if iscoroutine(result):
                            result = await result
                        results.append(
                            ToolMessage(tool_call_id=call.id, content=str(result))
                        )
                    except Exception as ex:
                        logger().error(
                            f"There was an error executing tool function {fname}: {ex}"
                        )
                        results.append(
                            ToolMessage(
                                tool_call_id=call.id,
                                content=f"There was an error executing tool function {fname}: {ex}. Try to fix the error or continue without it.",
                            )
                        )
            return results

    async def _execute_openai_function(self, message: AIMessage) -> FunctionMessage:
        function_call = message.additional_kwargs.get("function_call", None)
        if function_call:
            function_call = Function(**function_call)
            fname = function_call.name
            func = get_function(fname)
            if func:
                try:
                    result = func(**function_call.arguments)
                    if iscoroutine(result):
                        result = await result
                    return FunctionMessage(content=str(result), name=fname)
                except Exception as ex:
                    logger().error(
                        f"There was an error executing function {fname}: {ex}"
                    )
                    return FunctionMessage(
                        name=fname,
                        content=f"There was an error executing tool function {fname}: {ex}. Try to fix the error or continue without it.",
                    )

    def get_definition_generator(self):
        if self == FunctionCallSupport.OPENAI_FUNCTION:
            return convert_to_openai_function
        elif self == FunctionCallSupport.OPENAI_TOOL:
            return convert_to_openai_tool

        return None

    @cache
    def get_function_definition(self, func_name: str):
        generator = self.get_definition_generator()
        func = _FUNCTIONS_BY_NAME.get(func_name, None)
        return generator(func) if func else None

    def get_kwargs(self):
        app_config = AppConfig.get_instance()
        function_names = [
            name
            for name in _FUNCTIONS_BY_NAME.keys()
            if app_config.functions and name in app_config.functions
        ]
        definitions = [self.get_function_definition(name) for name in function_names]
        if definitions:
            if self == FunctionCallSupport.OPENAI_FUNCTION:
                return {"functions": definitions, "function_call": "auto"}
            elif self == FunctionCallSupport.OPENAI_TOOL:
                return {"tools": definitions, "tool_choice": "auto"}

        return {}


_DEFAULT_FUNCTION_CALL_SUPPORT = {
    # Specify which models for which api provider support which type of function calling.
    # This can be overwritten in the app config, in case new models get deployed
    # and this code cannot be updated in time
    "btp": {
        "gpt-4,gpt-4-turbo,gpt-35-turbo,gpt-35-turbo-16k,gpt-4-32k": FunctionCallSupport.OPENAI_FUNCTION
    },
    "openai": {"*": FunctionCallSupport.OPENAI_TOOL},
}


def load_function_entry_points():
    for entry_point in pkg_resources.iter_entry_points("gptextual_function"):
        # Just loading the entry point is enough if each function
        # is decorated with @register_for_function_calling below
        entry_point.load()


def get_function(function_name: str):
    return _FUNCTIONS_BY_NAME.get(function_name, None)


def register_for_function_calling(func):
    _FUNCTIONS_BY_NAME[func.__name__] = func
    return func


def get_function_config(func):
    fname = func if isinstance(func, str) else func.__name__
    return AppConfig.get_instance().functions.get(fname, None)
