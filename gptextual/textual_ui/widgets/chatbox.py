from __future__ import annotations

import re
from langchain.schema import BaseMessage, AIMessage

import pyperclip

from rich.console import RenderableType
from rich.markdown import Markdown
from textual.binding import Binding
from textual.geometry import Size
from textual.widget import Widget
from textual.containers import Container

from gptextual.textual_ui.screens.message_info_modal import MessageInfo
from gptextual.utils import format_timestamp
from gptextual.runtime.langchain.schema import new_message_of_type


class ChatboxContainer(Container):
    ...


class Chatbox(Widget, can_focus=True):
    BINDINGS = [
        Binding(
            key="ctrl+s",
            action="focus('cl-option-list')",
            description="Focus List",
            key_display="^s",
        ),
        Binding(
            key="i",
            action="focus('chat-input')",
            description="Focus Input",
            key_display="i",
        ),
        Binding(
            key="d", action="details", description="Message details", key_display="d"
        ),
        Binding(key="c", action="copy", description="Copy Message", key_display="c"),
        Binding(key="`", action="copy_code", description="Copy Code Blocks"),
    ]

    def __init__(
        self,
        *,
        model_name: str,
        message: BaseMessage | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )
        self._message = message or new_message_of_type(AIMessage)

        self.model_name = model_name
        timestamp = format_timestamp(
            self.message.additional_kwargs.get("timestamp", 0) or 0
        )
        self.tooltip = f"Sent {timestamp}"

    @property
    def is_ai_message(self):
        return self.message and self.message.type.lower().startswith("ai")

    def on_mount(self) -> None:
        if self.message.type.lower().startswith("ai"):
            self.add_class("assistant-message")

    def get_code_blocks(self, markdown_string):
        pattern = r"```(.*?)\n(.*?)```"
        code_blocks = re.findall(pattern, markdown_string, re.DOTALL)
        return code_blocks

    def action_copy_code(self):
        codeblocks = self.get_code_blocks(self.message.content)
        output = ""
        if codeblocks:
            for lang, code in codeblocks:
                output += f"{code}\n\n"
            pyperclip.copy(output)
            self.notify("Codeblocks have been copied to clipboard", timeout=3)
        else:
            self.notify("There are no codeblocks in the message to copy", timeout=3)

    def action_copy(self) -> None:
        pyperclip.copy(self.message.content)
        self.notify("Message content has been copied to clipboard", timeout=3)

    def action_details(self) -> None:
        self.app.push_screen(
            MessageInfo(message=self.message, model_name=self.model_name)
        )

    @property
    def markdown(self) -> Markdown:
        return Markdown(self.message.content or "")

    def render(self) -> RenderableType:
        return self.markdown

    def get_content_width(self, container: Size, viewport: Size) -> int:
        # Naive approach. Can sometimes look strange, but works well enough.
        content = self.message.content or ""
        return min(len(content), container.width)

    @property
    def message(self):
        return self._message

    @message.setter
    def message(self, m):
        if not isinstance(m, BaseMessage):
            raise ValueError("Message must be a BaseMessage instance")
        self._message = m
