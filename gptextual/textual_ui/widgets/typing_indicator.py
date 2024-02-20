from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import LoadingIndicator, Label


class IsTyping(Horizontal):
    def compose(self) -> ComposeResult:
        yield LoadingIndicator()
        yield Label("  AI is responding ")
