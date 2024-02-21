from __future__ import annotations

import glob
import os
from pathlib import Path
from dataclasses import dataclass
import threading

from gptextual.logging import logger

from .models import ChatModel
from .conversation import Conversation, conversation_path


@dataclass
class ConversationManager:
    conversations = {}
    # Needed so we can monkey patch in an extension package
    conversation_class = Conversation

    @classmethod
    def load_conversations_from_storage(cls):
        # Get a list of all JSON files in the storage path
        files = glob.glob(str(conversation_path / "*.json"))

        if len(files):
            cls.conversations = {
                key: val
                for key, val in (
                    (Path(file).stem, cls.conversation_class.load(Path(file).stem))
                    for file in files
                )
                if val is not None
            }

    @classmethod
    def save_all(cls):
        def do_save():
            for conversation in ConversationManager.all_conversations():
                try:
                    conversation.save(in_background=False)
                except Exception as ex:
                    logger().error(f"Error saving conversations, {ex}")

        save_thread = threading.Thread(target=do_save)
        save_thread.start()

    @classmethod
    def delete_conversation(cls, id: str):
        header_file = conversation_path / f"{id}.json"
        messages_file = conversation_path / f"{id}.parquet"
        try:
            os.remove(header_file)
            os.remove(messages_file)
        except FileNotFoundError:
            pass
        except Exception as e:
            logger().error(f"Error deleting conversation with id {id}: {e}")
        if id in cls.conversations:
            del cls.conversations[id]

    @classmethod
    def all_conversations(cls):
        return list(
            sorted(
                [data for data in cls.conversations.values()],
                key=lambda x: x.update_time,
                reverse=True,
            )
        )

    @classmethod
    def get_conversation(cls, conversation_id: str):
        return cls.conversations.get(conversation_id, None)

    @classmethod
    def create_conversation(cls, *, model: ChatModel, system_message=None) -> str:
        conv = cls.conversation_class.create_new(
            model=model,
            system_message=system_message,
        )
        cls.conversations[conv.id] = conv
        return conv.id
