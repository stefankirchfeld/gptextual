from __future__ import annotations

from dataclasses import dataclass
from langchain.schema import (
    BaseMessage,
    HumanMessage,
)

from shortuuid import ShortUUID

from textual import on, events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical, VerticalScroll, Horizontal
from textual.message import Message
from textual.reactive import var
from textual.widget import Widget
from textual.widgets import TextArea, Button

from gptextual.config import AppConfig
from gptextual.runtime import (
    ConversationManager,
    Conversation,
    StreamingMessage,
    AppContext,
)
from gptextual.runtime.langchain.schema import new_message_of_type

from gptextual.textual_ui.widgets.typing_indicator import IsTyping
from gptextual.textual_ui.widgets.header import ChatHeader
from gptextual.textual_ui.widgets.model_select import ModelSelect
from gptextual.textual_ui.widgets.chatbox import Chatbox, ChatboxContainer


class ChatInputArea(TextArea):
    BINDINGS = [
        Binding(
            key="ctrl+s",
            action="focus('cl-option-list')",
            description="Focus List",
            key_display="^s",
        ),
        Binding(
            key="ctrl+f",
            action="search",
            description="Search",
            key_display="^f",
        ),
    ]

    class Submit(Message):
        def __init__(self, textarea: ChatInputArea) -> None:
            super().__init__()
            self.input_area = textarea

        @property
        def control(self):
            return self.input_area

    def __init__(self, chat: Chat, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.chat = chat

    def _on_focus(self, event: events.Focus) -> None:
        super()._on_focus(event)
        self.chat.scroll_to_latest_message()

    def action_search(self):
        self.screen.action_search()


class Chat(Widget):
    DEFAULT_CSS = """
    .multiline {
      height: 8;
    } 
    .singleline {
      height: 3;
    }
    
    
    """
    allow_input_submit = var(True)
    """Used to lock the chat input while the agent is responding."""

    def __init__(self) -> None:
        super().__init__()

        self.chat_container: ScrollableContainer | None = None
        self.chat_options: ModelSelect = ModelSelect()
        self.chat_id = None
        self.input_area = ChatInputArea(self, id="chat-input", classes="singleline")
        self.responding_indicator = IsTyping()
        self.responding_indicator.display = False
        self.multiline = False

        # needed for search
        self.chatboxes_by_id = {}
        self.uuid_gen = ShortUUID()

    @dataclass
    class FirstMessageSent(Message):
        chat_data: Conversation

    @dataclass
    class MessageSubmitted(Message):
        chat_id: str

    @dataclass
    class AIResponseReceived(Message):
        chat_id: str
        message: BaseMessage

    def compose(self) -> ComposeResult:
        yield ChatHeader()
        with Vertical(id="chat-input-container"):
            with Horizontal(id="chat-input-text-container"):
                yield self.input_area
                yield Button("Send", id="btn-submit")
            yield self.responding_indicator

        with VerticalScroll(id="chat-scroll-container") as vertical_scroll:
            self.chat_container = vertical_scroll
            vertical_scroll.can_focus = False

        yield self.chat_options

    @on(TextArea.Changed)
    def on_input_changed(self, event: TextArea.Changed):
        area = self.input_area

        def update_height(height):
            s = "singleline"
            m = "multiline"
            multiline = height > 1
            if multiline != self.multiline:
                self.multiline = multiline
                area.set_class(multiline, m)
                area.set_class(not multiline, s)
                self.refresh(layout=True)

        height = self.input_area.get_content_height(None, None, None)
        update_height(height)

    @on(ChatInputArea.Submit)
    async def user_chat_message_submitted(self, event: ChatInputArea.Submit) -> None:
        if self.allow_input_submit is True:
            user_message = event.input_area.text
            if len(user_message):
                event.input_area.clear()
                await self.chat(user_message)

    @property
    def current_conversation(self) -> Conversation:
        return (
            None
            if self.chat_id is None
            else ConversationManager.get_conversation(self.chat_id)
        )

    def scroll_to_latest_message(self):
        if self.chat_container is not None:
            self.chat_container.refresh()
            self.chat_container.scroll_end(animate=False)

    def update_header(self, *, title=None, model_name=None, api_provider=None):
        chat = self.current_conversation
        chat_header = self.query_one(ChatHeader)
        chat_header.title = title or (chat and chat.short_preview) or "New Chat..."
        chat_header.model_name = (
            (model_name and api_provider and f"{model_name}@{api_provider}")
            or (chat and f"{chat.model.name}@{chat.model.api_provider}")
            or ""
        )

    async def mount_chat_boxes(self, boxes: list[Chatbox]):
        for box in boxes:
            self.chatboxes_by_id[
                box.message.additional_kwargs.get("id", self.uuid_gen.random(20))
            ] = box
        containers = [
            ChatboxContainer(
                box, classes=("assistant-message" if box.is_ai_message else None)
            )
            for box in boxes
        ]
        await self.chat_container.mount_all(containers)

    async def load_conversation(self, chat_id: str) -> None:
        if chat_id is None:
            return

        if not self.chat_options.display and chat_id == self.chat_id:
            return

        assert self.chat_options is not None
        assert self.chat_container is not None

        # If the options display is visible, get rid of it.
        self.chat_options.display = False

        # Update the chat data
        await self.clear_chat_view()
        self.chat_id = chat_id

        chat = self.current_conversation
        model_name = chat.model.name
        chat_boxes = [
            Chatbox(model_name=model_name, message=message)
            for message in chat.displayable_messages
        ]

        stream_message = chat.streaming_message
        if stream_message:
            chat_boxes.append(
                Chatbox(model_name=model_name, message=stream_message.message)
            )
            # By binding the current stream to the new chatbox, we can resume the stream
            # even after the user navigated to another conversation in between
            self._bind_stream_to_chatbox(chatbox=chat_boxes[-1], conversation=chat)
            self.allow_input_submit = False
        else:
            self.allow_input_submit = True

        await self.mount_chat_boxes(chat_boxes)
        # await self.chat_container.mount_all(chat_boxes)
        self.chat_container.scroll_end(animate=False)
        self.update_header()

    async def prepare_for_new_chat(self) -> None:
        await self.clear_chat_view()
        self.update_header()
        self.chat_options.display = True

    async def clear_chat_view(self) -> None:
        assert self.chat_container is not None
        if self.current_conversation:
            self.current_conversation.on_stream_chunk = None
        self.chat_id = None
        self.chatboxes_by_id.clear()
        # Copy list to not modify list during loop
        children = list(self.chat_container.children)
        for child in children:
            await child.remove()

    async def chat(self, content: str) -> None:
        if not self.app.app_context.current_model:
            self.notify("No model selected", title="Error", severity="error", timeout=5)
            return

        message = new_message_of_type(HumanMessage, content=content)
        message.additional_kwargs["id"] = self.uuid_gen.random(20)
        await self.progress_conversation(message)

    async def progress_conversation(self, message: BaseMessage) -> None:
        new_chat = self.chat_id is None
        if new_chat:
            assert self.chat_options is not None
            self.chat_options.display = False
            self.chat_id = ConversationManager.create_conversation(
                model=self.app.app_context.current_model,
                system_message=self.app.app_context.system_message,
            )
            self.update_header(
                title=Conversation.preview_from_messages([message]),
            )

        assert self.chat_id is not None
        assert message is not None

        user_message_chatbox = Chatbox(
            message=message, model_name=self.current_conversation.model.name
        )

        assert self.chat_container is not None
        await self.mount_chat_boxes([user_message_chatbox])
        # await self.chat_container.mount(user_message_chatbox)
        self.scroll_to_latest_message()

        self.responding_indicator.display = True
        self.allow_input_submit = False

        def stream_in_background():
            self.run_worker(
                self._stream_llm_response(
                    conversation=self.current_conversation, message=message
                ),
                group="llm_stream",
                exclusive=False,
            )

        self.app.call_after_refresh(stream_in_background)

    async def _stream_llm_response(
        self, *, conversation: Conversation, message: BaseMessage
    ) -> None:
        response: BaseMessage = None
        response_chatbox = None

        async def create_response_chatbox():
            response_chatbox = Chatbox(model_name=conversation.model.name)
            assert (
                self.chat_container is not None
            ), "Textual has mounted container at this point in the lifecycle."
            await self.mount_chat_boxes([response_chatbox])
            self._bind_stream_to_chatbox(
                chatbox=response_chatbox, conversation=conversation
            )
            return response_chatbox

        async for resp in conversation.progress(message):
            response = resp
            if response_chatbox is None:
                chunk = response
                if isinstance(response, StreamingMessage):
                    chunk = response.message
                response_chatbox = await create_response_chatbox()
                await conversation.on_stream_chunk(chunk, 0)
            if isinstance(response, BaseMessage):
                """
                This logic ensures that a conversation can also create more than one
                full response messages. 
                """
                if "id" in response_chatbox.message.additional_kwargs:
                    self.chatboxes_by_id[
                        response_chatbox.message.additional_kwargs["id"]
                    ] = response_chatbox
                response_chatbox = None
                conversation.on_stream_chunk = None

        self.responding_indicator = self.query_one(IsTyping)
        self.responding_indicator.display = False
        self.allow_input_submit = True
        self.post_message(
            self.AIResponseReceived(chat_id=conversation.id, message=response)
        )
        self.input_area.focus()

    def _bind_stream_to_chatbox(
        self, *, chatbox: Chatbox, conversation: Conversation
    ) -> None:
        """
        Creates a closure which is bound to the given chatbox widget.

        It is set on the conversation object as the on_stream_chunk callback.
        This way, when a user switches chats while an LLM is streaming a response,
        the stream can later be resumed by creating a new closure for a new chatbox widget.
        The new widget will then display the current stream.
        """
        config = AppConfig.get_instance().textual

        async def func(chunk, chunk_no, chatbox=chatbox):
            if isinstance(chunk, StreamingMessage):
                chatbox.message = chunk.message
                if chunk_no == 0:
                    self.post_message(self.MessageSubmitted(self.chat_id))
                if chunk_no % config.refresh_no_stream_chunks == 0:
                    scroll = True
                else:
                    scroll = False
            elif isinstance(chunk, BaseMessage):
                chatbox.message = chunk
                scroll = True

            if scroll:
                chatbox.refresh(layout=True)
                scroll_y = self.chat_container.scroll_y
                max_scroll_y = self.chat_container.max_scroll_y
                if scroll_y in range(max_scroll_y - 3, max_scroll_y + 1):
                    self.chat_container.scroll_end(animate=False)

        conversation.on_stream_chunk = func

    async def on_mount(self, _: events.Mount) -> None:
        """
        When the component is mounted, we need to check if there is a new chat to start
        """
        app_context: AppContext = self.app.app_context  # type: ignore[attr-defined]
        if app_context.chat_message is not None:
            await self.prepare_for_new_chat()
            await self.chat(app_context.chat_message)
            self.input_area.focus()

    @on(Button.Pressed, selector="#btn-submit")
    def on_submit(self, event: Button.Pressed):
        event.stop()
        self.input_area.post_message(ChatInputArea.Submit(self.input_area))
