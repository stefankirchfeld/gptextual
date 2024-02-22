import glob
from pathlib import Path
import os
import threading
import logging
from collections import deque
from types import SimpleNamespace
from datetime import datetime
from dataclasses import dataclass, field
import json
from typing import List
import polars as pl

from langchain_core.messages import (
    AIMessageChunk,
    BaseMessage,
    AIMessage,
    HumanMessage,
    FunctionMessage,
    ToolMessage,
    SystemMessage,
)
from langchain_core.outputs import ChatGenerationChunk
from langchain_core.language_models import BaseLanguageModel


from shortuuid import ShortUUID

from gptextual.runtime.langchain.schema import (
    is_function_or_tool_call,
    is_tool_related_message,
)
from gptextual.runtime.function_calling import FunctionCallSupport
from gptextual.runtime.models import ModelRegistry, ChatModel
from gptextual.logging import logger


@dataclass
class StreamingMessage:
    message: BaseMessage = None
    additional_kwargs: dict = field(
        default_factory=lambda: {"timestamp": datetime.utcnow().timestamp()}
    )


def ensure_list(x):
    if not isinstance(x, list):
        return [x]
    return x


conversation_path = Path.home() / (".gptextual") / "conversations"
export_path = Path.home() / (".gptextual") / "exports"
MESSAGE_COLUMNS = SimpleNamespace(
    id="id", type="type", content="content", additionals="additional_kwargs"
)


@dataclass
class Conversation:
    id: str | None
    model: ChatModel
    title: str | None
    create_timestamp: float | None

    # In-memory conversations can be used for functions that spawn
    # side conversations with different LLMs. These should not be persisted.
    in_memory: bool = False
    messages: list[BaseMessage] = field(init=False, default_factory=list)

    def __post_init__(self):
        self._on_chunk_callback = None
        self._dirty = False
        self._messages_lock = threading.Lock()
        self.uuid_gen = ShortUUID()

    def __len__(self):
        return len(self.messages)

    def __iter__(self):
        return iter(self.messages)

    def set_dirty(self):
        self._dirty = True
        Conversation.search_df = None

    def append(self, message: BaseMessage | List[BaseMessage]):
        message = ensure_list(message)
        with self._messages_lock:
            for m in message:
                if "id" not in m.additional_kwargs:
                    m.additional_kwargs["id"] = self.uuid_gen.random(20)
                self.messages.append(m)
        self.set_dirty()

    @property
    def first_user_message(self) -> BaseMessage | None:
        for m in self.messages:
            if isinstance(m, HumanMessage):
                return m

    def last_message_of_types(self, *types):
        for m in reversed(self.messages):
            if isinstance(m, tuple(types)):
                return m
        return None

    @property
    def short_preview(self):
        if self.title:
            return self.title[:30]
        return Conversation.preview_from_messages(messages=self.messages)

    @property
    def displayable_messages(self) -> list[BaseMessage]:
        return [
            m
            for m in self.messages
            if not isinstance(
                m, (StreamingMessage, SystemMessage, ToolMessage, FunctionMessage)
            )
            and not is_function_or_tool_call(m)
        ]

    @property
    def create_time(self) -> datetime:
        return datetime.fromtimestamp(self.create_timestamp or 0).astimezone()

    @property
    def update_time(self) -> datetime:
        create_time = self.create_time.timestamp()
        return datetime.fromtimestamp(
            self.messages[-1].additional_kwargs.get("timestamp", create_time)
            if self.messages
            else create_time
        ).astimezone()

    @property
    def streaming_message(self):
        if not len(self):
            return None
        return (
            self.messages[-1]
            if isinstance(self.messages[-1], StreamingMessage)
            else None
        )

    @property
    def on_stream_chunk(self):
        return self._on_chunk_callback

    @on_stream_chunk.setter
    def on_stream_chunk(self, cb):
        self._on_chunk_callback = cb

    def has_messages_of_types(self, *types):
        return any([isinstance(m, tuple(types)) for m in self.messages])

    def progress(self, messages: BaseMessage | List[BaseMessage], *, autosave=True):
        return self._progress_llm(messages=messages, autosave=autosave)

    async def _progress_llm(
        self, messages: BaseMessage | List[BaseMessage], *, autosave=True
    ):
        try:
            if self.streaming_message:
                logger().info(
                    f"Conversation {self.title or self.id} is already streaming, but another message was sent to it: {messages}"
                )
                return

            messages = ensure_list(messages)

            for m in messages:
                if isinstance(m, (AIMessage, SystemMessage)):
                    raise ValueError(
                        "Conversation can only be progressed by human or function/tool messages"
                    )

            self.append(messages)
            response = StreamingMessage()
            self.append(response)
            chunks = 0
            async for chunk in self._stream_llm(
                self._messages_for_context_size(self.messages)[:-1]
            ):
                response.message = (
                    chunk if response.message is None else response.message + chunk
                )

                if self.on_stream_chunk:
                    await self.on_stream_chunk(response, chunks)
                chunks += 1
                yield response

            self.messages.pop()
            response = response.message
            if response:
                self.append(response)

            function_calling = FunctionCallSupport.forModelName(
                model_name=self.model.name, api_provider=self.model.api_provider
            )
            function_results = (
                await function_calling.execute_function_call(response)
                if function_calling
                else None
            )

            if function_results:
                async for resp in self._progress_llm(function_results, autosave=False):
                    response = resp
                    yield response
            else:
                response.additional_kwargs["timestamp"] = datetime.utcnow().timestamp()
                if self.on_stream_chunk:
                    await self.on_stream_chunk(response, chunks)
                yield response

            if autosave:
                self.save(in_background=True)

        except Exception as ex:
            logger().error(f"Error progressing the LLM conversation: {ex}")
            yield AIMessageChunk(content=f"There was conversation error, {ex}")

    async def _stream_llm(self, messages):
        try:
            function_kwargs = {}
            function_calling = FunctionCallSupport.forModelName(
                model_name=self.model.name, api_provider=self.model.api_provider
            )
            if function_calling:
                function_kwargs = function_calling.get_kwargs()

            if logger().getEffectiveLevel() <= logging.INFO:
                log_msg = messages[-3:] if len(messages) >= 3 else [*messages]
                log_msg.reverse()
                logger().info(
                    f"Calling model {self.model.name}@{self.model.api_provider}",
                    extra={
                        "last_3_messages": [
                            {
                                "type": m.type,
                                "content": m.content,
                                "kwargs": m.additional_kwargs,
                            }
                            for m in log_msg
                        ],
                        "functions": function_kwargs,
                    },
                )

            def to_message(chunk):
                if isinstance(chunk, str):
                    return AIMessageChunk(content=chunk)
                if isinstance(chunk, BaseMessage):
                    return chunk
                elif isinstance(chunk, ChatGenerationChunk):
                    return chunk.message

                raise ValueError(
                    f"Cannot get message from unknown chunk type {chunk.__class__}"
                )

            async for chunk in self.model.llm_model.astream(
                messages, **function_kwargs
            ):
                try:
                    yield to_message(chunk)
                except Exception as ex:
                    raise ex
        except Exception as ex:
            logger().error(f"Error during LLM streaming: {ex}")
            yield AIMessageChunk(
                content=f"There was an error streaming the LLM response, {ex}"
            )

    def _get_message_length(self, message: BaseMessage) -> int:
        if isinstance(message, StreamingMessage):
            return self.model.default_max_tokens
        else:
            model_name = self.model.name
            model = self.model.llm_model
            return Conversation.get_num_tokens_from_messages(
                messages=message, model_name=model_name, model=model
            )[0]

    def _messages_for_context_size(
        self, messages: list[BaseMessage]
    ) -> list[BaseMessage]:
        """Returns a list of messages that fit within the context window."""

        if not messages:
            return []

        context_messages = deque()

        system_message = messages[0] if isinstance(messages[0], SystemMessage) else None
        length_available = self.model.context_window
        if system_message:
            length_available -= self._get_message_length(system_message)
            if length_available < 0:
                raise ValueError("System message is too long for context window")

        for message in reversed(messages):
            message_length = self._get_message_length(message)
            if message_length <= length_available:
                context_messages.appendleft(message)
                length_available -= message_length
            else:
                break

        if context_messages and context_messages[0] is not system_message:
            context_messages.appendleft(system_message)

        return list(context_messages)

    def save(self, in_background=True):
        if self.in_memory:
            return

        def do_save():
            try:
                if not self._dirty:
                    return

                data = {
                    "id": self.id,
                    "model": self.model.name,
                    "api_provider": self.model.api_provider,
                    "title": self.title,
                    "create_timestamp": self.create_timestamp,
                }

                # Save the data to a JSON file
                with open(conversation_path / f"{self.id}.json", "w") as f:
                    json.dump(data, f)

                rows = {
                    MESSAGE_COLUMNS.id: [],
                    MESSAGE_COLUMNS.type: [],
                    MESSAGE_COLUMNS.content: [],
                    MESSAGE_COLUMNS.additionals: [],
                }

                # Filter out tool related messages
                with self._messages_lock:
                    messages = list(
                        filter(lambda m: not is_tool_related_message(m), self.messages)
                    )
                    self.messages = messages

                for m in messages:
                    rows[MESSAGE_COLUMNS.id].append(m.additional_kwargs["id"])
                    rows[MESSAGE_COLUMNS.type].append(m.type)
                    rows[MESSAGE_COLUMNS.content].append(m.content)
                    rows[MESSAGE_COLUMNS.additionals].append(
                        json.dumps(m.additional_kwargs)
                    )
                df = pl.DataFrame(rows)
                df.write_parquet(conversation_path / f"{self.id}.parquet")
                self._dirty = False
            except Exception as ex:
                logger().error(
                    f"There was an error saving the conversation {self.id}: {ex}"
                )

        if in_background:
            save_thread = threading.Thread(target=do_save)
            # Start the new thread
            save_thread.start()
        else:
            do_save()

    def export_to_markdown(self):
        # Create the markdown header
        create_time = datetime.fromtimestamp(self.create_timestamp).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        header = f"# Conversation: {self.title}\n"
        header += f"Model: {self.model.name}\n\n"
        header += f"API Provider: {self.model.api_provider}"
        header += f"Created At: {create_time}\n"
        header += "\n---\n\n"  # Add a horizontal rule for styling

        def message_prefix(m):
            type = m.type
            type = type.lower()

            if type.startswith("human"):
                return "Human"
            elif type.startswith("ai"):
                return "AI"
            elif type.startswith("system"):
                return "System"
            elif type.startswith("tool"):
                return "Tool"
            elif type.startswith("func"):
                return "Function"

        # Create markdown entries for each message
        messages_md = ""
        for message in self.messages:
            prefix = f"**{message_prefix(message)}**\n\n"
            messages_md += f"{prefix}{message.content}\n\n"

        # Combine the header and messages
        markdown_content = header + messages_md

        # Write the markdown content to a file
        markdown_path = export_path / f"{self.model.name}_{create_time}.md"
        with open(markdown_path, "w", encoding="utf-8") as md_file:
            md_file.write(markdown_content)
        return markdown_path

    @classmethod
    def search(cls, query: str) -> pl.DataFrame:
        if cls.search_df is None:
            try:
                files = glob.glob(str(conversation_path / "*.parquet"))

                search_df = None
                for file in files:
                    filepath = Path(file)
                    conv_id = filepath.stem
                    header_file = conversation_path / f"{conv_id}.json"
                    header_data = None
                    with open(header_file, "r") as f:
                        header_data = json.load(f)

                    if (
                        header_data is None
                        or ModelRegistry.get_instance().model_from_name(
                            header_data["model"], header_data["api_provider"]
                        )
                        is None
                    ):
                        continue

                    df = (
                        pl.read_parquet(filepath)
                        .filter(~(pl.col(MESSAGE_COLUMNS.type) == "system"))
                        .select(MESSAGE_COLUMNS.id, MESSAGE_COLUMNS.content)
                        .with_columns(
                            pl.lit(conv_id).alias("conv_id"),
                            pl.col(MESSAGE_COLUMNS.content)
                            .str.to_lowercase()
                            .alias("search_content"),
                        )
                    )
                    search_df = (
                        pl.concat([search_df, df]) if search_df is not None else df
                    )
            except Exception as ex:
                logger().error(f"Error loading conversation search data: {ex}")

            if search_df is not None:
                cls.search_df: pl.DataFrame = search_df
            else:
                cls.search_df = pl.DataFrame(
                    schema=[
                        (MESSAGE_COLUMNS.id, pl.Utf8),
                        (MESSAGE_COLUMNS.content, pl.Utf8),
                        ("conv_id", pl.Utf8),
                        ("search_content", pl.Utf8),
                    ]
                )

        res = (
            cls.search_df.filter(
                pl.col("search_content").str.contains(query.lower(), literal=True)
            )
            .select(MESSAGE_COLUMNS.id, "conv_id", MESSAGE_COLUMNS.content)
            .head(20)
        )
        return res

    @classmethod
    def load(cls, id: str):
        try:
            header_file = conversation_path / f"{id}.json"
            messages_file = conversation_path / f"{id}.parquet"

            if not os.path.exists(header_file) or not os.path.exists(messages_file):
                raise ValueError(
                    f"Conversation {id} cannot be loaded. Files do not exist."
                )

            # Load the data from the JSON file
            with open(header_file, "r") as f:
                data = json.load(f)

            # Replace the 'model' attribute with the actual model
            data["model"] = ModelRegistry.get_instance().model_from_name(
                data["model"], data["api_provider"]
            )

            if not data["model"]:
                return None
            del data["api_provider"]
            # Create a new Conversation object from the loaded data
            conv = cls(**data)
            df = pl.read_parquet(messages_file)
            for row in df.rows(named=True):
                type, content, kwargs = (
                    row[MESSAGE_COLUMNS.type],
                    row[MESSAGE_COLUMNS.content],
                    row[MESSAGE_COLUMNS.additionals],
                )
                kwargs = {"content": content, "additional_kwargs": json.loads(kwargs)}
                type = type.lower()
                message = None

                if type.startswith("human"):
                    message = HumanMessage(**kwargs)
                elif type.startswith("ai"):
                    message = AIMessage(**kwargs)
                elif type.startswith("system"):
                    message = SystemMessage(**kwargs)
                elif type.startswith("tool"):
                    message = ToolMessage(**kwargs)
                elif type.startswith("func"):
                    message = FunctionMessage(**kwargs)

                if message:
                    conv.messages.append(message)

            conv._dirty = False
            return conv
        except Exception as ex:
            logger().error(f"There was an error loading conversation {id}: {ex}")
            return None

    @staticmethod
    def preview_from_messages(messages: list) -> str:
        first_user_message = [m for m in messages if isinstance(m, HumanMessage)]
        first_user_message = first_user_message[0] if len(first_user_message) else None
        if not first_user_message:
            return "Empty chat..."
        first_content = first_user_message.content or ""
        return first_content[:30] + "..."

    @classmethod
    def create_new(
        cls,
        *,
        model: ChatModel,
        title: str = None,
        system_message: str = None,
        in_memory: bool = False,
    ):
        if model is None:
            raise ValueError("No model provided for conversation")

        _system_message = f"""
The current UTC datetime is {datetime.utcnow()}.
Do not escape markdown as codeblocks using '`' chars.Messages will be rendered as markdown by default!
"""
        if system_message is not None:
            _system_message += f"{system_message}\n{_system_message}"
        conv = cls(
            id=ShortUUID().random(20),
            model=model,
            title=title,
            create_timestamp=datetime.utcnow().timestamp(),
            in_memory=in_memory,
        )
        conv.append(SystemMessage(content=_system_message))
        return conv

    @staticmethod
    def get_num_tokens_from_messages(
        *,
        messages: BaseMessage | list[BaseMessage],
        model_name: str,
        model: BaseLanguageModel,
    ) -> list[int]:
        messages = ensure_list(messages)

        if not messages:
            return 0

        try:
            return [model.get_num_tokens_from_messages(messages=[m]) for m in messages]
        except Exception as ex:
            logger().error(
                f"Error calculating number of token messages for model {model_name}: {ex}. Falling back on estimate."
            )
            # Cannot get exact token count...do very(!) rough estimation.
            return [int(len(m.content) / 3.5) for m in messages]


Conversation.search_df = None
