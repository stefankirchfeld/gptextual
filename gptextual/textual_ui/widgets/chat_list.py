from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass

import humanize
from rich.console import RenderResult, Console, ConsoleOptions
from rich.style import Style
from rich.color import Color
from rich.padding import Padding
from rich.text import Text
from textual import log, on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.binding import Binding
from textual.reactive import var
from textual.widget import Widget
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option, Separator

from gptextual.textual_ui.widgets.footer import CommandFooter, Command, Field
from gptextual.runtime import ConversationManager


@dataclass
class ChatListItemRenderable:
    chat_id: str
    is_open: bool = False

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        chat = ConversationManager.get_conversation(self.chat_id)
        delta = datetime.utcnow().astimezone() - chat.update_time
        subtitle = humanize.naturaltime(delta)
        yield Padding(
            Text.assemble(
                (chat.short_preview, "" if not self.is_open else "b"),
                "\n\n",
                (f"{chat.model.name}@{chat.model.api_provider}", "i"),
                "\n",
                (subtitle, Style(color=Color.from_rgb(128, 128, 128))),
            ),
            pad=(0, 1),
            style="reverse" if self.is_open else "",
        )


class ChatListItem(Option):
    def __init__(self, chat_id: str, is_open: bool = False) -> None:
        """
        Args:
            chat: The chat associated with this option.
            is_open: True if this is the chat that's currently open.
        """
        super().__init__(ChatListItemRenderable(chat_id=chat_id, is_open=is_open))
        self.chat_id = chat_id
        self.is_open = is_open


class ChatList(Widget):
    BINDINGS = [
        Binding(
            "i",
            action="focus('chat-input')",
            description="Focus Input",
            key_display="i",
        ),
        Binding("r", "rename_conversation", "Rename Chat", key_display="r"),
        Binding("d", "delete_conversation", "Delete Chat", key_display="d"),
        Binding("e", "export", "Export To Markdown", key_display="e"),
    ]
    COMPONENT_CLASSES = {"app-title", "app-subtitle"}

    current_chat_id: var[str | None] = var(None)

    @dataclass
    class ChatOpened(Message):
        chat_id: str

    @dataclass
    class ChatDeleted(Message):
        chat_id: str

    def compose(self) -> ComposeResult:
        with Vertical(id="cl-header-container"):
            yield Static(
                Text(
                    "GPTextual",
                    style=self.get_component_rich_style("app-title"),
                )
            )
            yield Static(
                Text(
                    "LLMs in the Terminal",
                    style=self.get_component_rich_style("app-subtitle"),
                )
            )

        self.options = self.load_conversation_list_items()
        option_list = OptionList(
            *self.options,
            id="cl-option-list",
        )
        yield option_list

        with Horizontal(id="cl-button-container"):
            yield Button("New Chat", id="cl-new-chat-button")

    @on(OptionList.OptionSelected, "#cl-option-list")
    def post_chat_opened(self, event: OptionList.OptionSelected) -> None:
        assert isinstance(event.option, ChatListItem)
        self.post_message(ChatList.ChatOpened(chat_id=event.option.chat_id))
        self.current_chat_id = event.option.chat_id

    def watch_current_chat_id(self, old_chat_id: str, new_chat_id: str):
        if old_chat_id != new_chat_id:
            self.reload_and_refresh()

    def action_rename_conversation(self):
        if self.current_chat_id:
            footer: CommandFooter = self.app.query_one(CommandFooter)
            if footer.command:
                return

            conv = ConversationManager.get_conversation(self.current_chat_id)

            def rename(values):
                title: str = values[0]
                if title:
                    conv.title = title
                    conv.set_dirty()
                    conv.save()
                    self.reload_and_refresh()
                self.query_one("#cl-option-list").focus()

            fields = (
                Field(
                    "Title",
                    str,
                    has_spaces=True,
                    value=conv.title or conv.short_preview,
                ),
            )
            footer.command = Command("New Title", fields, rename)
            self.screen.set_focus(footer)

    def action_delete_conversation(self):
        if self.current_chat_id:
            footer: CommandFooter = self.app.query_one(CommandFooter)
            if footer.command:
                return

            def delete_chat(values):
                confirm: bool = values[0]
                if confirm:
                    ConversationManager.delete_conversation(self.current_chat_id)
                    self.post_message(
                        ChatList.ChatDeleted(chat_id=self.current_chat_id)
                    )
                    self.current_chat_id = None
                self.query_one(OptionList).focus()

            fields = (Field("yes/no", bool),)
            footer.command = Command("Delete this Chat?", fields, delete_chat)
            self.screen.set_focus(footer)

    def action_export(self):
        if self.current_chat_id:
            chat = ConversationManager.get_conversation(self.current_chat_id)
            path = chat.export_to_markdown()
            self.notify(
                f"Chat was saved as markdown at {path}",
                title="Export successful",
                timeout=10,
            )

    def on_focus(self) -> None:
        log.debug("Sidebar focused")
        self.query_one("#cl-option-list", OptionList).focus()

    def reload_and_refresh(self) -> None:
        """Reload the chats and refresh the widget. Can be used to
        update the ordering/previews/titles etc contained in the list.

        Args:
            new_highlighted: The index to highlight after refresh.
        """
        self.options = self.load_conversation_list_items()
        highlighted_idx = 0
        for idx, item in enumerate(self.options):
            if not isinstance(item, Separator) and item.chat_id == self.current_chat_id:
                highlighted_idx = idx // 2
        option_list = self.query_one(OptionList)
        option_list.clear_options()
        option_list.add_options(self.options)
        option_list.highlighted = highlighted_idx

    def load_conversation_list_items(self) -> list[ChatListItem]:
        chats = ConversationManager.all_conversations()
        ans = []
        for chat in chats:
            ans.append(ChatListItem(chat.id, is_open=self.current_chat_id == chat.id))
            ans.append(Separator())
        return ans
