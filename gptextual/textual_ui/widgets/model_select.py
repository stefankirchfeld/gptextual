from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static, Select, TextArea

from gptextual.runtime import ChatModel, ModelRegistry


class ModelSelect(Widget, can_focus=True):
    BINDINGS = [
        Binding(
            key="ctrl+s",
            action="focus('cl-option-list')",
            description="Focus List",
            key_display="^s",
        ),
    ]

    DEFAULT_CSS = """
    
    #system-message-label {
      margin-top: 1;
    }
    
    TextArea {
      height: 15;
      width: 50%;
      min-width: 8;
    }
    """

    class ModelSelected(Message):
        def __init__(self, model: ChatModel, system_message: str = None):
            super().__init__()
            self.model = model
            self.system_message = system_message

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        registry = ModelRegistry.get_instance()
        default_model: ChatModel = registry.default_model
        if len(registry):
            self.provider_select = Select(
                id="provider-select",
                options=sorted(
                    [(p, p) for p in registry.models if len(registry.models[p])],
                    key=lambda x: x[0],
                ),
                allow_blank=False if default_model else True,
                value=default_model.api_provider if default_model else None,
            )
            self.model_select = Select(
                id="model-select",
                options=sorted(
                    [
                        (model.name, model)
                        for model in registry.models_for_provider(
                            default_model.api_provider
                        )
                    ]
                    if default_model
                    else [],
                    key=lambda x: x[0],
                ),
                allow_blank=False if default_model else True,
                value=default_model,
            )
        else:
            self.provider_select = Static(
                "There are no models configured in `~/.gptextual/config.yml`. Check the README on how to configure API providers and models."
            )
            self.model_select = None

    def _update_app_context(self, model: ChatModel = None, system_message: str = None):
        if model:
            self.post_message(self.ModelSelected(model=model))
            self.app.app_context.model_name = model.name
            self.app.app_context.api_provider = model.api_provider

        if system_message is not None:
            self.app.app_context.system_message = system_message

    def _update_model_select(self, api_provider: str):
        registry = ModelRegistry.get_instance()
        options = list(
            sorted(
                [
                    (model.name, model)
                    for model in registry.models_for_provider(api_provider)
                ],
                key=lambda x: x[0],
            )
        )
        self.model_select.set_options(options)
        self.model_select.expanded = True
        self.model_select.refresh(layout=True)
        self._update_app_context(model=self.model_select.value)

    @on(Select.Changed, "#provider-select")
    def provider_selected(self, event: Select.Changed) -> None:
        self._update_model_select(event.value)

    @on(Select.Changed, "#model-select")
    def model_selected(self, event: Select.Changed) -> None:
        self._update_app_context(model=self.model_select.value)

    @on(TextArea.Changed, "#system-message-input")
    def on_system_message_change(self, event: TextArea.Changed) -> None:
        self._update_app_context(system_message=event.text_area.text)

    def compose(self) -> ComposeResult:
        with Vertical(id="chat-options-container"):
            if self.model_select:
                yield Static(
                    "Select an API provider and model. Then just start chatting to create a new conversation.",
                    id="model-select-label",
                )
                yield self.provider_select
                yield self.model_select
                yield Static("System Message (optional)", id="system-message-label")
                yield TextArea(id="system-message-input")
            else:
                yield self.provider_select
