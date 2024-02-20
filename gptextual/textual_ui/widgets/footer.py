from typing import Any
from dataclasses import dataclass
import inspect

from textual.widgets import Footer, Input, Label
from textual.containers import Horizontal, Vertical
from rich.console import RenderableType
from textual.reactive import reactive

from gptextual.utils import single_css_class


@dataclass
class Field:
    name: str
    type: Any
    has_spaces: bool = False
    value: str = ""

    def __str__(self):
        return f"<{self.name}: {self.type.__name__}>"


@dataclass
class Command:
    name: str
    fields: tuple
    on_submit: object


newline_char = "\n"


class CommandFooter(Footer):
    height_pct = [
        single_css_class(f"h-pct-{val}", "height", f"{val}%")
        for val in range(0, 110, 10)
    ]
    height = [single_css_class(f"h-{val}", "height", f"{val}") for val in range(0, 11)]
    width_pct = [
        single_css_class(f"w-pct-{val}", "width", f"{val}%")
        for val in range(0, 110, 10)
    ]
    OTHER_CSS = """
      #command_input {
        min-height: 4;
      }
      .align-center {
        align: center middle;
      } 

      .ml-2 {
        margin-left: 2;
      }
    """

    DEFAULT_CSS = f"""
    {newline_char.join(height_pct)}
    {newline_char.join(height)} 
    {newline_char.join(width_pct)}
    {OTHER_CSS}
    """

    command: Command = reactive(None)

    def __init__(self, *args, **kwds) -> None:
        super().__init__(*args, **kwds)
        self.height_class = "h-4"

    def render(self) -> RenderableType:
        if self.command is not None:
            return ""

        return super().render()

    def watch_command(self, command: Command):
        self.update(command)

    @property
    def value(self):
        if self.command:
            ans = [f.value for f in self.command.fields if f.value]
            return " ".join(ans)

        return None

    @property
    def placeholder(self):
        if self.command:
            ans = [str(f) for f in self.command.fields]
            return " ".join(ans)
        return None

    def _extract_values(self, *args):
        if len(args) == 0 or args[0] is None:
            return None

        values = []
        for i in range(-1, -(len(self.command.fields) + 1), -1):
            field: Field = self.command.fields[i]
            if field.has_spaces:
                if i == -1:
                    values.append(" ".join(args))
                else:
                    values.append(" ".join(args[: i + 1]))
                break
            else:
                if field.type == bool:
                    values.append(args[i].lower() in ("y", "yes", "true"))
                else:
                    values.append(field.type(args[i]))

        return tuple(reversed(values))

    def update(self, command: Command):
        if command is None:
            try:
                container = self.query_one("#command_footer")
                container.remove()
            except Exception:
                pass
            self.remove_class(self.height_class)
            return

        input_field = Input(value=self.value, placeholder="", classes="w-pct-100 h-3")

        children = []

        children.append(
            Horizontal(
                Label(command.name, classes="align-center"),
                Vertical(
                    input_field,
                    Label(self.placeholder, classes="w-pct-100 h-1 ml-2"),
                    classes="w-pct-100 h-pct-100",
                ),
                classes="align-center h-pct-20",
                id="command_input",
            ),
        )

        self.mount(
            Vertical(
                *children,
                id="command_footer",
                classes="align-center h-pct-100 w-pct-100",
            )
        )
        self.add_class(self.height_class)
        self.screen.set_focus(input_field)

    def _on_key(self, event) -> None:
        if event.key == "escape":
            self.command = None

    async def on_input_submitted(self, message: Input.Submitted):
        if self.command is None:
            return
        try:
            callback = self.command.on_submit
            tokens = message.value.split(" ")
            values = self._extract_values(*tokens)
            ans = callback(values)
            if inspect.iscoroutine(ans):
                await ans
        except Exception:
            pass

        self.command = None
