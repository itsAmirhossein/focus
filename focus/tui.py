"""Textual UI: dashboard, task detail, add form."""

from __future__ import annotations

import webbrowser

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Footer,
    Input,
    Label,
    OptionList,
    RadioButton,
    RadioSet,
    Static,
)
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
OWNER_LABEL = {"me": "👨‍💻 Me", "claude": "🤖 Claude"}

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
    indent = " " * (len(task["id"]) + 4)
    prompt = Text.assemble(
        "  ",
        (task["id"], "bold"),
        "  ",
        task["title"],
        "\n",
        indent,
        (STATUS_LABEL[task["status"]], STATUS_STYLE[task["status"]]),
        "   ",
        OWNER_LABEL[task["owner"]],
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


def _open_url(screen: Screen, url: str) -> None:
    if not url:
        screen.notify("No URL for this task.", severity="warning")
        return
    webbrowser.open(url)  # macOS: osascript "open location" -> default browser
    screen.notify(f"Opened {url}")


class Board(Screen):
    BINDINGS = [
        Binding("a", "add", "Add"),
        Binding("r", "reload", "Reload"),
        Binding("q", "quit", "Quit"),
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
        Binding("o", "open_task", "Task URL"),
        Binding("m", "open_mr", "MR URL"),
        Binding("s", "set_status('working')", "Start"),
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
            yield Static(f"{task.get('id', '')} — {task.get('title', '')}", id="detail-title")
            yield Static(self._body())
            with Horizontal(classes="row"):
                yield Button("Open Task", id="open_task", disabled=not task.get("url"))
                yield Button("Open MR", id="open_mr", disabled=not task.get("mr_url"))
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
        body = Text.assemble(
            "\nStatus:  ",
            (STATUS_LABEL[status], STATUS_STYLE[status]),
            "\nOwner:   ",
            OWNER_LABEL[task.get("owner", "me")],
        )
        if task.get("url"):
            body.append(f"\n\n🔗 Task\n{task['url']}")
        if task.get("mr_url"):
            body.append(f"\n\n🔀 Merge Request\n{task['mr_url']}")
        return body

    def on_mount(self) -> None:
        if not self.task_data:
            self.notify(f"Task {self.task_id} is gone.", severity="error")
            self.dismiss()

    def action_back(self) -> None:
        self.dismiss()

    def action_open_task(self) -> None:
        _open_url(self, self.task_data.get("url", ""))

    def action_open_mr(self) -> None:
        _open_url(self, self.task_data.get("mr_url", ""))

    def action_set_status(self, status: str) -> None:
        storage.set_status(self.task_id, status)
        self.app.notify(f"{self.task_id} → {status.upper()}")
        self.dismiss()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id in self.BUTTON_STATUS:
            self.action_set_status(self.BUTTON_STATUS[button_id])
        elif button_id == "open_task":
            self.action_open_task()
        elif button_id == "open_mr":
            self.action_open_mr()
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
            yield Input(placeholder="Task ID", id="task_id")
            yield Input(placeholder="Task title", id="task_title")
            yield Label("Owner  (↑↓ move, space selects)")
            with RadioSet(id="owner"):
                yield RadioButton(OWNER_LABEL["me"], value=True)
                yield RadioButton(OWNER_LABEL["claude"])
            yield Input(placeholder="Task URL (optional)", id="task_url")
            yield Input(placeholder="MR URL (optional)", id="task_mr_url")
            with Horizontal(classes="row"):
                yield Button("Save", variant="success", id="save")
                yield Button("Cancel", id="cancel")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#task_id", Input).focus()

    def _value(self, widget_id: str) -> str:
        return self.query_one(f"#{widget_id}", Input).value.strip()

    def action_save(self) -> None:
        task_id, title = self._value("task_id"), self._value("task_title")
        if not task_id or not title:
            self.notify("Task ID and title are required.", severity="error")
            return
        task = {
            "id": task_id,
            "title": title,
            "status": "todo",
            "owner": "claude" if self.query_one(RadioSet).pressed_index == 1 else "me",
            "url": self._value("task_url"),
            "mr_url": self._value("task_mr_url"),
        }
        if not storage.add(task):
            self.notify(f"Task {task_id} already exists.", severity="error")
            return
        self.dismiss(task)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "task_mr_url":
            self.action_save()
        else:
            self.focus_next()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self.action_save()
        else:
            self.dismiss(None)


class BoardApp(App):
    CSS = CSS
    TITLE = "focus"

    def on_mount(self) -> None:
        self.push_screen(Board())


class AddApp(App[dict | None]):
    CSS = CSS
    TITLE = "focus add"

    def on_mount(self) -> None:
        self.push_screen(AddScreen(), callback=self.exit)


def run_board() -> None:
    BoardApp().run()


def run_add() -> dict | None:
    return AddApp().run()
