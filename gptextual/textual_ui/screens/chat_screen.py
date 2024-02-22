from pathlib import Path

from textual import on, log
from textual.app import ComposeResult
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.events import Mount
from textual.screen import Screen
from textual.widgets import Button

from gptextual.runtime.conv_manager import ConversationManager
from gptextual.textual_ui.screens.search_screen import SearchScreen
from gptextual.textual_ui.widgets.chatbox import Chatbox
from gptextual.textual_ui.widgets.footer import CommandFooter
from gptextual.textual_ui.widgets.chat import Chat
from gptextual.textual_ui.widgets.header import ChatHeader
from gptextual.textual_ui.widgets.chat_list import ChatList
from gptextual.textual_ui.widgets.model_select import ModelSelect
from gptextual.textual_ui.screens.log_screen import LogScreen
from gptextual.textual_ui.widgets.search import Search


class ChatScreen(Screen):
    BINDINGS = [
        Binding("q", "quit", "Quit App", key_display="q"),
        Binding("ctrl+n", action="new_chat", description="New Chat", key_display="^n"),
        Binding("ctrl+f", action="search", description="Search", key_display="^f"),
        Binding(
            "ctrl+l", action="open_log", description="Show Log File", key_display="^l"
        ),
    ]

    def __init__(self):
        super().__init__()
        self.chat = Chat()
        self.log_screen = None

    def compose(self) -> ComposeResult:
        yield ChatList(id="chat-list")
        yield self.chat
        yield CommandFooter()

    async def on_mount(self, event: Mount) -> None:
        all_conversations = ConversationManager.all_conversations()
        if len(all_conversations):
            chat_list = self.query_one(ChatList)
            chat_list.current_chat_id = all_conversations[0].id
            await self.chat.load_conversation(chat_list.current_chat_id)

    @on(Chat.MessageSubmitted)
    def user_message_submitted(self, event: Chat.MessageSubmitted) -> None:
        # ChatList ordering will change, so we need to force an update...
        chat_list = self.query_one(ChatList)
        chat_list.current_chat_id = event.chat_id

    @on(Chat.AIResponseReceived)
    def on_ai_response(self, event: Chat.AIResponseReceived) -> None:
        chat_list = self.query_one(ChatList)
        chat_list.current_chat_id = event.chat_id
        # Calling this explictly in order to refresh the ordering of chats
        # in the list
        chat_list.reload_and_refresh()

    @on(ChatList.ChatOpened)
    async def on_chat_opened(self, event: ChatList.ChatOpened) -> None:
        self.chat.allow_input_submit = False
        await self.chat.load_conversation(event.chat_id)
        chat_list = self.query_one(ChatList)
        chat_list.current_chat_id = event.chat_id
        self.chat.allow_input_submit = True

    @on(ChatList.ChatDeleted)
    async def on_chat_deleted(self, event: ChatList.ChatDeleted) -> None:
        await self.action_new_chat()

    @on(Button.Pressed, "#cl-new-chat-button")
    async def on_new_chat_button(self, event: Button.Pressed):
        await self.action_new_chat()

    @on(Search.SearchResultSelected)
    async def on_search_selected(self, event: Search.SearchResultSelected):
        conv_id, message_id = event.conversation_id, event.message_id
        with self.app.batch_update():
            self.app.pop_screen()
            await self.on_chat_opened(ChatList.ChatOpened(conv_id))
            chat_box: Chatbox = self.chat.chatboxes_by_id.get(message_id, None)
            if chat_box:
                chat_box.focus(scroll_visible=True)

    def action_search(self):
        self.app.push_screen(SearchScreen(self))

    @on(ModelSelect.ModelSelected)
    def update_model(self, event: ModelSelect.ModelSelected) -> None:
        model = event.model

        try:
            conversation_header = self.query_one(ChatHeader)
        except NoMatches:
            log.error("Couldn't find ConversationHeader to update model name.")
        else:
            conversation_header.model_name = f"{model.name}@{model.api_provider}"

    async def action_new_chat(self) -> None:
        chat = self.query_one(Chat)
        await chat.prepare_for_new_chat()
        chat.chat_options.provider_select.focus()

    def action_open_log(self) -> None:
        self.app.push_screen(LogScreen())


class ChatScreenDark(ChatScreen):
    CSS_PATH = Path(__file__).parent.parent / "dark.tcss"


class ChatScreenLight(ChatScreen):
    CSS_PATH = Path(__file__).parent.parent / "light.tcss"
