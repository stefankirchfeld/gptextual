from textual.app import ComposeResult
from textual.screen import Screen
from textual.binding import Binding
from textual.widget import Widget


from gptextual.textual_ui.widgets.search import Search


class SearchScreen(Screen):
    BINDINGS = [Binding("escape", "close", "Close", show=False)]

    DEFAULT_CSS = """
    SearchScreen {
      background: $panel 90%;
      content-align: center top;
      align: center top;
      width: 100%;
      height: 100%;
    }
    
    SearchScreen Search {
      width: 60;
      margin-top: 15;
      align: center middle;
      content-align: center middle;
      background: black 0%;
    }
    
  """

    def __init__(self, parent: Widget = None, *args, **kwds) -> None:
        super().__init__(*args, **kwds)
        self.search = Search(parent)

    def action_close(self):
        self.app.pop_screen()

    def on_mount(self):
        search = self.query_one(Search)
        search.input_field.focus()

    def compose(self) -> ComposeResult:
        yield self.search
