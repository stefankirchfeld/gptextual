from __future__ import annotations

import json
from langchain.schema import BaseMessage
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll, Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, Tabs, ContentSwitcher, Tab

from gptextual.utils import format_timestamp
from gptextual.textual_ui.widgets.token_analysis import TokenAnalysis


class MessageInfo(ModalScreen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Close Modal")]

    def __init__(
        self,
        message: BaseMessage,
        model_name: str,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(
            name=name,
            id=id,
            classes=classes,
        )
        self.message = message
        self.model_name = model_name
        self.token_analysis = TokenAnalysis(
            text=self.message.content or "", model_name=model_name, id="tokens"
        )

    def compose(self) -> ComposeResult:
        with Vertical(id="outermost-container"):
            with Horizontal(id="message-info-header"):
                yield Tabs(
                    Tab("Markdown", id="markdown-content"),
                    Tab("Tokens", id="tokens"),
                    Tab("Additional Data", id="metadata"),
                )

            with VerticalScroll(id="inner-container"):
                with ContentSwitcher(initial="markdown-content"):
                    yield Static(self.message.content or "", id="markdown-content")
                    yield self.token_analysis
                    yield Static(
                        json.dumps(self.message.additional_kwargs, indent=4),
                        id="metadata",
                    )

            with Horizontal(id="message-info-footer"):
                if self.model_name:
                    token_count = len(self.token_analysis.tokens)

                timestamp = self.message.additional_kwargs.get("timestamp", 0)
                timestamp_string = format_timestamp(timestamp)
                yield Static(f"Message sent at {timestamp_string}", id="timestamp")
                yield Static(f"{token_count} tokens", id="token-count")

    @on(Tabs.TabActivated)
    def tab_activated(self, event: Tabs.TabActivated) -> None:
        self.query_one(ContentSwitcher).current = event.tab.id
