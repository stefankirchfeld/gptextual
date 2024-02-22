from dataclasses import dataclass
from typing import Optional

from langchain_core.language_models import BaseLanguageModel

from gptextual.config.app_config import APIProviderConfig

from gptextual.config import AppConfig, APIProvider


@dataclass
class ChatModel:
    name: str
    api_provider: str
    context_window: int = 4097
    _model: BaseLanguageModel = None

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, o: object) -> bool:
        return isinstance(o, ChatModel) and o.name == self.name

    @property
    def default_max_tokens(self):
        return int(min(self.context_window * 0.1, 2000))

    @property
    def llm_model(self):
        if not self._model:
            config = AppConfig.get_instance()
            api_provider_config: APIProviderConfig = getattr(
                config.api_config, self.api_provider
            )
            if api_provider_config is None:
                raise ValueError(
                    f"Configuration Error: There is no app configuration for API provider {self.api_provider}"
                )

            kwargs = {"temperature": 0.6}
            if self.api_provider == APIProvider.GOOGLE:
                kwargs["max_output_tokens"] = self.default_max_tokens
            else:
                kwargs["max_tokens"] = self.default_max_tokens

            self._model = api_provider_config.create_model_instance(self.name, **kwargs)

        return self._model


class ModelRegistry:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ModelRegistry()
        return cls._instance

    def register_model(self, *, api_provider: str, model: ChatModel):
        self.models[api_provider][model.name] = model

    @classmethod
    def model_from_name(cls, name: str, api_provider: APIProvider):
        inst = cls.get_instance()
        if api_provider in inst.models:
            return inst.models[api_provider].get(name, None)

        return None

    def initialize_models_for_provider(self, api_provider: str):
        app_config = AppConfig.get_instance()
        api_config = getattr(app_config.api_config, api_provider.replace("-", "_"))
        if api_config:
            models: dict = api_config.models
            self.models = {
                **self.models,
                api_provider: {
                    **{
                        name: ChatModel(
                            name=name,
                            api_provider=api_provider,
                            context_window=conf.context_window,
                        )
                        for name, conf in models.items()
                    },
                },
            }

    def __init__(self) -> None:
        self.models = {}
        for api_provider in APIProvider:
            self.initialize_models_for_provider(api_provider.value)

    def __len__(self):
        n_models = 0
        for api_provider in self.models:
            n_models += len(self.models[api_provider])

        return n_models

    def all_models(self):
        for api_provider in self.models:
            for model in self.models[api_provider].values():
                yield model

    def models_for_provider(self, api_provider: str):
        if api_provider in self.models:
            for model in self.models[api_provider].values():
                yield model

    @property
    def default_model(self) -> ChatModel:
        ans = ModelRegistry.model_from_name("gpt-3.5-turbo", APIProvider.OPEN_AI)
        if ans is None:
            for m in self.all_models():
                return m
        return ans


@dataclass
class AppContext:
    """
    App Context
    """

    chat_message: Optional[str] = None
    model_name: str = None
    api_provider: str = None
    system_message: str = None

    @property
    def current_model(self) -> ChatModel:
        registry = ModelRegistry.get_instance()
        if self.model_name is None:
            return registry.default_model
        model = ModelRegistry.model_from_name(self.model_name, self.api_provider)
        if model is None:
            raise ValueError(
                f"Current Model {self.model_name}@{self.api_provider} not found"
            )
        return model
