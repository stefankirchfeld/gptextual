from __future__ import annotations

import os
from enum import Enum
import yaml
from pathlib import Path
from typing import Optional, Dict
import json

from langchain_core.language_models import BaseLanguageModel
from pydantic import BaseModel

try:
    from langchain_openai import ChatOpenAI as LangChainChatOpenAI
except ImportError:
    LangChainChatOpenAI = None

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None

try:
    from gen_ai_hub.proxy.langchain.init_models import (
        init_llm as sap_genai_create_langchain_llm,
    )
    from gen_ai_hub.proxy.core.proxy_clients import set_proxy_version
except ImportError:
    sap_genai_create_langchain_llm = None
    set_proxy_version = None

from gptextual.logging import logger

SIZE_4K = 4096
SIZE_8K = 8192
SIZE_16K = 16385
SIZE_32K = 32768
SIZE_128K = 128000


class APIProvider(str, Enum):
    SAP_GEN_AI = "gen-ai-hub"
    OPEN_AI = "openai"
    GOOGLE = "google"


class TextualConfig(BaseModel):
    refresh_no_stream_chunks: int = 3
    theme: Optional[str] = "light"


class ModelConfig(BaseModel):
    context_window: Optional[int] = SIZE_4K


class APIProviderConfig(BaseModel):
    function_call_support: Optional[Dict[str, str]] = {}
    models: Optional[Dict[str, ModelConfig | None]] = {}

    def create_config_file(self):
        ...

    def _write_config_file(self, *, folder: Path, filename: str, payload: str):
        os.makedirs(folder, exist_ok=True)
        with open(folder / filename, "w") as f:
            f.write(payload)

    def create_model_instance(self, model_name: str, **kwargs) -> BaseLanguageModel:
        return None


class GenAIHubConfig(APIProviderConfig):
    client_id: str
    client_secret: str
    auth_url: str
    api_base: str
    resource_group: str

    def create_config_file(self):
        folder = Path.home() / ".aicore"
        filename = "config.json"
        payload = {
            "AICORE_CLIENT_ID": self.client_id,
            "AICORE_CLIENT_SECRET": self.client_secret,
            "AICORE_AUTH_URL": self.auth_url,
            "AICORE_BASE_URL": self.api_base,
            "AICORE_RESOURCE_GROUP": self.resource_group,
        }
        self._write_config_file(
            folder=folder, filename=filename, payload=json.dumps(payload)
        )

    def create_model_instance(self, model_name: str, **kwargs) -> BaseLanguageModel:
        if set_proxy_version:
            set_proxy_version(APIProvider.SAP_GEN_AI.value)
        return (
            sap_genai_create_langchain_llm(model_name, **kwargs)
            if sap_genai_create_langchain_llm
            else None
        )


class OpenAIConfig(APIProviderConfig):
    api_key: str
    models: Optional[Dict[str, ModelConfig | None]] = {
        "gpt-4-0125-preview": ModelConfig(context_window=SIZE_128K),
        "gpt-4-turbo-preview": ModelConfig(context_window=SIZE_128K),
        "gpt-4": ModelConfig(context_window=SIZE_8K),
        "gpt-3.5-turbo-0125": ModelConfig(context_window=SIZE_16K),
        "gpt-3.5-turbo": ModelConfig(context_window=SIZE_4K),
    }

    def create_model_instance(self, model_name: str, **kwargs) -> BaseLanguageModel:
        return (
            LangChainChatOpenAI(model=model_name, openai_api_key=self.api_key, **kwargs)
            if LangChainChatOpenAI
            else None
        )


class GoogleConfig(APIProviderConfig):
    api_key: str
    models: Optional[Dict[str, ModelConfig | None]] = {
        "gemini-pro": ModelConfig(context_window=30720)
    }

    def create_model_instance(self, model_name: str, **kwargs) -> BaseLanguageModel:
        return (
            ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=self.api_key,
                convert_system_message_to_human=True,
                **kwargs,
            )
            if ChatGoogleGenerativeAI
            else None
        )


class APIConfig(BaseModel):
    gen_ai_hub: Optional[GenAIHubConfig] = None
    openai: Optional[OpenAIConfig] = None
    google: Optional[GoogleConfig] = None

    def _create_config_files(self):
        if self.gen_ai_hub:
            self.gen_ai_hub.create_config_file()


_instance: AppConfig = None


class AppConfig(BaseModel):
    functions: Optional[Dict[str, Optional[Dict[str, str]]]] = {}
    textual: Optional[TextualConfig] = TextualConfig()
    api_config: Optional[APIConfig] = APIConfig()
    log_level: Optional[str] = "INFO"

    @staticmethod
    def get_instance() -> AppConfig:
        global _instance
        if _instance is None:
            _instance = AppConfig.load_config()
            if _instance.api_config:
                _instance.api_config._create_config_files()
        return _instance

    @staticmethod
    def load_config() -> AppConfig:
        config_path = Path.home() / ".gptextual" / "config.yml"
        if config_path.exists():
            config_data = None
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)
            return AppConfig(**config_data) if config_data else AppConfig()
        else:
            # If the file is not found, return a default AppConfig instance
            logger().info(
                f"Configuration file not found at {config_path}. Using default settings."
            )
            return AppConfig()
