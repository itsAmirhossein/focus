"""Textual UI: dashboard, task detail, add form."""

from __future__ import annotations

import os

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from . import storage

STATUS_LABEL = {
    "todo": "⚪ TODO",
    "working": "🟡 WORKING",
    "self-review": "🟣 SELF-REVIEW",
    "review": "🔵 REVIEW",
    "blocked": "🔴 BLOCKED",
    "done": "✓ DONE",
}
STATUS_STYLE = {
    "todo": "dim",
    "working": "yellow",
    "self-review": "magenta",
    "review": "blue",
    "blocked": "red",
    "done": "green",
}

# Dashboard groups, in the order they answer "what am I working on right now?".
GROUPS = (
    ("ACTIVE", ("working", "self-review")),
    ("REVIEW", ("review",)),
    ("BLOCKED", ("blocked",)),
    ("TODO", ("todo",)),
    ("DONE", ("done",)),
)

CSS = """
#title {
    border: round $accent;
    text-align: center;
    text-style: bold;
    color: $accent;
    margin: 1 2 0 2;
}

#board {
    height: 1fr;
    margin: 0 1;
    border: none;
    background: $surface;
}

#detail { border: round $accent; margin: 1 2; padding: 0 1; }
#detail-title { text-style: bold; color: $accent; }
.row { height: auto; padding-top: 1; }
.row Button { margin-right: 1; }

AddScreen { align: center middle; }
#add-box {
    width: 66;
    height: auto;
    max-height: 90%;
    padding: 1 2;
    border: round $accent;
    background: $surface;
}
#add-box Label { text-style: bold; }
"""


def _task_option(task: dict) -> Option:
    prompt = Text.assemble(
        "  ",
        task["title"],
        "\n    ",
        (STATUS_LABEL[task["status"]], STATUS_STYLE[task["status"]]),
    )
    return Option(prompt, id=task["id"])


def _board_options(tasks: list[dict]) -> tuple[list, int | None]:
    """Build the grouped option list; also report the index of the first task."""
    options: list = []
    for label, statuses in GROUPS:
        options.append(Option(Text(label, style="bold"), disabled=True))
        group = [t for t in tasks if t["status"] in statuses]
        if not group:
            options.append(Option(Text("  None", style="dim"), disabled=True))
        options.extend(_task_option(task) for task in group)
        options.append(None)  # separator: drawn as a divider, not an option

    # Separators take no index, so count them out before locating the first task.
    rows = [option for option in options if option is not None]
    first_task = next((i for i, option in enumerate(rows) if option.id), None)
    return options, first_task


class Board(Screen):
    BINDINGS = [
        Binding("a", "add", "Add"),
        Binding("r", "reload", "Reload"),
        # "app." prefix required: action_quit lives on App, not on this screen.
        Binding("q", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("MY FOCUS", id="title")
        yield OptionList(id="board")
        yield Footer()

    def on_mount(self) -> None:
        self.reload()

    def reload(self) -> None:
        board = self.query_one("#board", OptionList)
        options, first_task = _board_options(storage.load())
        board.clear_options()
        board.add_options(options)
        board.focus()
        if first_task is not None:
            # After the refresh, or the list overwrites the highlight and the
            # first Enter lands on nothing.
            self.call_after_refresh(setattr, board, "highlighted", first_task)

    def action_reload(self) -> None:
        self.reload()

    def action_add(self) -> None:
        self.app.push_screen(AddScreen(), callback=lambda _: self.reload())

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id:
            self.app.push_screen(Detail(event.option_id), callback=lambda _: self.reload())


class Detail(Screen):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("s","set_status('working')", "Start"),
        Binding("f", "set_status('self-review')", "Self-rev"),
        Binding("v", "set_status('review')", "Review"),
        Binding("d", "set_status('done')", "Done"),
        Binding("b", "set_status('blocked')", "Block"),
    ]

    BUTTON_STATUS = {
        "s_working": "working",
        "s_self_review": "self-review",
        "s_review": "review",
        "s_done": "done",
        "s_blocked": "blocked",
    }

    def __init__(self, task_id: str) -> None:
        super().__init__()
        self.task_id = task_id
        self.task_data = storage.get(task_id) or {}

    def compose(self) -> ComposeResult:
        task = self.task_data
        with VerticalScroll(id="detail"):
            yield Static(task.get("title", ""), id="detail-title")
            yield Static(self._body())
            with Horizontal(classes="row"):
                yield Button("Start", id="s_working")
                yield Button("Self-review", id="s_self_review")
                yield Button("Review", id="s_review")
            with Horizontal(classes="row"):
                yield Button("Done", id="s_done", variant="success")
                yield Button("Block", id="s_blocked", variant="error")
                yield Button("Back", id="back")
        yield Footer()

    def _body(self) -> Text:
        task = self.task_data
        status = task.get("status", "todo")
        return Text.assemble("\nStatus:  ", (STATUS_LABEL[status], STATUS_STYLE[status]))

    def on_mount(self) -> None:
        if not self.task_data:
            self.notify("That task is gone.", severity="error")
            self.dismiss()

    def action_back(self) -> None:
        self.dismiss()

    def action_set_status(self, status: str) -> None:
        storage.set_status(self.task_id, status)
        self.app.notify(f"{self.task_data['title']} → {status.upper()}")
        self.dismiss()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id in self.BUTTON_STATUS:
            self.action_set_status(self.BUTTON_STATUS[button_id])
        else:
            self.dismiss()


class AddScreen(ModalScreen[dict | None]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save"),
    ]

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="add-box"):
            yield Label("New task")
            yield Input(placeholder="Task title", id="task_title")
            with Horizontal(classes="row"):
                yield Button("Save", variant="success", id="save")
                yield Button("Cancel", id="cancel")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#task_title", Input).focus()

    def action_save(self) -> None:
        title = self.query_one("#task_title", Input).value.strip()
        if not title:
            self.notify("A title is required.", severity="error")
            return
        self.dismiss(storage.add(title))

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.action_save()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self.action_save()
        else:
            self.dismiss(None)


def _apply_theme(app: App) -> None:
    """$FOCUS_THEME picks a Textual theme; ctrl+p switches for one session only."""
    theme = os.environ.get("FOCUS_THEME")
    if theme and theme in app.available_themes:
        app.theme = theme


class BoardApp(App):
    CSS = CSS
    TITLE = "focus"

    def on_mount(self) -> None:
        _apply_theme(self)
        self.push_screen(Board())


class AddApp(App[dict | None]):
    CSS = CSS
    TITLE = "focus add"

    def on_mount(self) -> None:
        _apply_theme(self)
        self.push_screen(AddScreen(), callback=self.exit)


def run_board() -> None:
    BoardApp().run()


def run_add() -> dict | None:
    return AddApp().run()
