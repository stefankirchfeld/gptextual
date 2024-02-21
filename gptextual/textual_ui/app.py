import os
from typing import Optional

from textual.app import App

from toolong.watcher import get_watcher

from gptextual.logging import setup_logging, log_path
from gptextual.config import AppConfig
from gptextual.runtime.function_calling.function_call_support import (
    load_function_entry_points,
)
from gptextual.runtime.models import AppContext
from gptextual.runtime.conv_manager import ConversationManager
from gptextual.runtime.conversation import conversation_path, export_path

from gptextual.textual_ui.screens import ChatScreenDark, ChatScreenLight
from gptextual.textual_ui.widgets.footer import CommandFooter, Command, Field


class GPTextual(App):
    def __init__(self, context: Optional[AppContext] = None) -> None:
        super().__init__()
        app_config = AppConfig.get_instance()
        setup_logging(app_config.log_level)
        load_function_entry_points()
        self.app_context = context or AppContext()
        os.makedirs(conversation_path, exist_ok=True)
        os.makedirs(export_path, exist_ok=True)
        ConversationManager.load_conversations_from_storage()

        # attributes to integrate TooLong log file app
        self.file_paths = [str(log_path / "gptextual.jsonl")]
        self.merge = True
        self.save_merge = False
        self.watcher = None

    def start_log_watcher(self):
        if self.watcher:
            return

        self.watcher = get_watcher()
        self.watcher.start()

    def stop_log_watcher(self):
        if self.watcher:
            self.watcher.close()
            self.watcher = None

    def action_quit(self):
        footer: CommandFooter = self.query_one(CommandFooter)
        if footer.command:
            return

        def exit(values):
            confirm: bool = values[0]
            if confirm:
                self.exit()

        fields = (Field("yes/no", bool),)
        footer.command = Command("Quit Application?", fields, exit)
        self.screen.set_focus(footer)

    def on_mount(self) -> None:
        config = AppConfig.get_instance().textual
        self.push_screen(
            ChatScreenLight() if config.theme == "light" else ChatScreenDark()
        )

    def on_unmount(self) -> None:
        self.stop_log_watcher()


def run():
    app = GPTextual()
    app.run()


if __name__ == "__main__":
    run()
