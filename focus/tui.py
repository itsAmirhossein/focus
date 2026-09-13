"""Textual UI: dashboard, task detail, add form."""

from __future__ import annotations

import os

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.markup import escape
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from . import storage

# status -> (icon, label, color). Theme variables keep the colors legible in every theme.
STATUS = {
    "todo": ("○", "To do", "$text-muted"),
    "working": ("●", "Working", "$warning"),
    "self-review": ("◐", "Self-review", "$warning"),
    "review": ("◆", "In review", "$primary"),
    "blocked": ("■", "Blocked", "$error"),
    "done": ("✓", "Done", "$success"),
}

# Dashboard groups, in the order they answer "what am I working on right now?".
GROUPS = (
    ("In progress", ("working", "self-review")),
    ("In review", ("review",)),
    ("Blocked", ("blocked",)),
    ("To do", ("todo",)),
    ("Done", ("done",)),
)

CSS = """
#top { height: auto; padding: 1 2; background: $boost; }
#brand { width: auto; margin-right: 4; text-style: bold; color: $accent; }
#summary { width: 1fr; }

#board, #board:focus {
    height: 1fr;
    max-height: 100%;
    border: none;
    padding: 0 1;
    background: $background;
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
    icon, label, color = STATUS[task["status"]]
    title = escape(task["title"])
    if task["status"] == "done":
        title = f"[dim strike]{title}[/]"
    elif task["status"] == "self-review":
        title += f"  [dim italic]{label.lower()}[/]"
    return Option(f"  [{color}]{icon}[/]  {title}", id=task["id"])


def _board_options(tasks: list[dict]) -> tuple[list[Option], int | None]:
    """Build the grouped option list, hiding empty groups; also report the first task's index."""
    options: list[Option] = []
    for name, statuses in GROUPS:
        group = [t for t in tasks if t["status"] in statuses]
        if not group:
            continue
        color = STATUS[statuses[0]][2]
        gap = "\n" if options else ""
        header = f"{gap}[bold {color}]{name.upper()}[/]  [dim]{len(group)}[/]"
        options.append(Option(header, disabled=True))
        options.extend(_task_option(task) for task in group)
    if not options:
        options.append(Option("  [dim]No tasks yet. Press [bold]a[/] to add one.[/]", disabled=True))
    first_task = next((i for i, option in enumerate(options) if option.id), None)
    return options, first_task


def _summary(tasks: list[dict]) -> str:
    """One line with every group's count, so the whole board reads at a glance."""
    parts = []
    for name, statuses in GROUPS:
        count = sum(t["status"] in statuses for t in tasks)
        icon, _, color = STATUS[statuses[0]]
        parts.append(f"[{color if count else '$text-disabled'}]{icon} {count} {name.lower()}[/]")
    return "   ".join(parts)


class Board(Screen):
    BINDINGS = [
        Binding("a", "add", "Add"),
        Binding("r", "reload", "Reload"),
        # "app." prefix required: action_quit lives on App, not on this screen.
        Binding("q", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        with Horizontal(id="top"):
            yield Static("focus", id="brand")
            yield Static(id="summary")
        yield OptionList(id="board")
        yield Footer()

    def on_mount(self) -> None:
        self.reload()

    def reload(self) -> None:
        tasks = storage.load()
        self.query_one("#summary", Static).update(_summary(tasks))
        board = self.query_one("#board", OptionList)
        options, first_task = _board_options(tasks)
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
            yield Static(task.get("title", ""), id="detail-title", markup=False)
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

    def _body(self) -> str:
        icon, label, color = STATUS[self.task_data.get("status", "todo")]
        return f"\nStatus:  [{color}]{icon} {label}[/]"

    def on_mount(self) -> None:
        if not self.task_data:
            self.notify("That task is gone.", severity="error")
            self.dismiss()

    def action_back(self) -> None:
        self.dismiss()

    def action_set_status(self, status: str) -> None:
        storage.set_status(self.task_id, status)
        self.app.notify(f"{self.task_data['title']} → {status.upper()}", markup=False)
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
