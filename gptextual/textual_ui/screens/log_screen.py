from __future__ import annotations


from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.lazy import Lazy
from textual.widgets import TabbedContent, TabPane
from textual.screen import Screen

from toolong.log_view import LogView
from toolong.help import HelpScreen


class LogScreen(Screen):
    BINDINGS = [
        Binding("q", action="close", description="Close"),
    ]

    CSS = """
    LogScreen {
        layers: overlay;
        & TabPane {           
            padding: 0;
        }
        & Tabs:focus Underline > .underline--bar {
            color: $accent;
        }        
        Underline > .underline--bar {
            color: $panel;
        }
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.app.start_log_watcher()

    async def on_mount(self) -> None:
        self.query("TabbedContent Tabs").set(display=len(self.query(TabPane)) > 1)
        active_pane = self.query_one(TabbedContent).active_pane
        if active_pane is not None:
            active_pane.query("LogView > LogLines").focus()

    def compose(self) -> ComposeResult:
        with TabbedContent():
            if self.app.merge and len(self.app.file_paths) > 1:
                tab_name = " + ".join(Path(path).name for path in self.app.file_paths)
                with TabPane(tab_name):
                    yield Lazy(
                        LogView(
                            self.app.file_paths,
                            self.app.watcher,
                            can_tail=False,
                        )
                    )
            else:
                for path in self.app.file_paths:
                    with TabPane(path):
                        yield Lazy(
                            LogView(
                                [path],
                                self.app.watcher,
                                can_tail=True,
                            )
                        )

    def action_help(self) -> None:
        self.app.push_screen(HelpScreen())

    def action_close(self):
        self.app.pop_screen()
        self.app.stop_log_watcher()
