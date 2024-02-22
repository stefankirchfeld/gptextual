# Parts of this code uses code from https://github.com/Textualize/toolong:

# MIT License

# Copyright (c) 2024 Will McGugan

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
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
