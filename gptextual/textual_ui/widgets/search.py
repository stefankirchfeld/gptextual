import threading

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Header, Input, OptionList
from textual.widgets.option_list import Option, Separator
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.message import Message
from textual import on
from textual.app import App

from gptextual.runtime import Conversation


class Search(Vertical):
    class SearchResultSelected(Message):
        def __init__(self, conversation_id: str, message_id: str) -> None:
            super().__init__()
            self.conversation_id = conversation_id
            self.message_id = message_id

    BINDINGS: list[BindingType] = [
        Binding("down", "cursor_down", "Down", show=False),
    ]

    DEFAULT_CSS = """

    .Search-expanded {
      height: 30;
    }

    Search {
      height: 3;
    }

    Search OptionList {
        border: tall $background;
        background: $panel;
        color: $text;
        padding: 0 1;

        width: 1fr;
        display: block;
        height: auto;
        max-height: 15;
        overlay: screen;
        constrain: y;
    }

    Search Input {
      width: 100%;
    }

  """

    def __init__(self, parent: Widget, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.timer = None
        self.parent_widget = parent

    @on(Input.Changed)
    def input_changed(self, event: Input.Changed):
        query = event.value
        if self.timer is not None:
            self.timer.cancel()

        # Create a new timer that calls the search method after a delay
        self.timer = threading.Timer(0.5, self.search, [query])
        self.timer.start()

    @on(OptionList.OptionSelected)
    def on_option_selected(self, event: OptionList.OptionSelected):
        conv_id, message_id = event.option_id
        widget = self.parent_widget if self.parent_widget else self
        widget.post_message(
            Search.SearchResultSelected(conversation_id=conv_id, message_id=message_id)
        )

    def set_options(self, options) -> None:
        select_options: list[Option] = [
            Option(prompt=prompt, id=value) for prompt, value in options
        ]

        option_list = self.query_one(OptionList)
        option_list.clear_options()
        for option in select_options:
            option_list.add_option(option)
            option_list.add_option(Separator())

    def action_cursor_down(self):
        input = self.query_one(Input)
        option_list = self.query_one(OptionList)
        if input.has_focus and option_list.option_count > 0:
            option_list.focus()
            option_list.highlighted = 0

    def break_into_lines(self, text, max_line_length):
        words = text.split(" ")
        lines = []
        current_line = []

        for word in words:
            if len(current_line) + len(word) + 1 <= max_line_length:
                current_line.append(word + " ")
            else:
                lines.append("".join(current_line).rstrip())
                current_line = [word + " "]

        # Add the last line if it's not empty
        if current_line:
            lines.append("".join(current_line).rstrip())

        return "\n".join(lines)

    def get_preview(self, content: str, query: str, max_line_length: 20):
        window_size = max(30, len(query))
        match_start_index = content.lower().find(query.lower())
        start_index = max(0, match_start_index - window_size)
        end_index = min(len(content), match_start_index + window_size + len(query))

        preview = f'{"..." if start_index > 0 else ""}{content[start_index:end_index]}{"..." if end_index < len(content) else ""}'

        return self.break_into_lines(preview, max_line_length=max_line_length)

    def search(self, query: str):
        results = []
        if query:
            df = Conversation.search(query)
            rows = df.rows(named=True)
            for row in rows:
                conv_id, message_id, content = row["conv_id"], row["id"], row["content"]
                results.append(
                    (
                        self.get_preview(content, query, max_line_length=30),
                        (conv_id, message_id),
                    )
                )

        options: OptionList = self.query_one(OptionList)
        self.set_options(results)
        expanded = len(results) > 0
        options.visible = expanded

        classname = "Search-expanded"
        if expanded:
            self.add_class(classname)
        else:
            self.remove_class(classname)

    @property
    def input_field(self):
        return self.query_one(Input)

    def compose(self) -> ComposeResult:
        options = OptionList(None)
        options.visible = False
        with Vertical():
            yield Input(placeholder="Search messages...")
            yield options


if __name__ == "__main__":

    class SelectApp(App):
        DEFAULT_CSS = """
    Screen {
      align: center top;
      background: blue;
    }

    Screen {
      background: blue;
    }
    Search {
      width: 60;
      margin: 2;
      background: $panel 0%;
    }
        """

        def compose(self) -> ComposeResult:
            yield Header()
            yield Search()

    app = SelectApp()
    app.run()
