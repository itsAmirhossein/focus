"""Textual UI: board, status picker, add form."""

from __future__ import annotations

import os

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.markup import escape
from textual.screen import ModalScreen, Screen
from textual.widgets import Footer, Input, Label, OptionList, Static
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

# One key per status, shared by the board and the picker so they never disagree.
MOVES = (
    ("s", "working", "Start"),
    ("f", "self-review", "Self-review"),
    ("v", "review", "Review"),
    ("b", "blocked", "Block"),
    ("t", "todo", "To do"),
    ("d", "done", "Done"),
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

StatusPicker, AddScreen { align: center middle; }
#picker, #add-box {
    width: 60;
    max-width: 90%;
    height: auto;
    padding: 1 2;
    border: round $accent;
    background: $surface;
}
#picker-title, #add-box Label { width: 100%; text-style: bold; margin-bottom: 1; }
#moves, #moves:focus { height: auto; border: none; padding: 0; background: $surface; }
.hint { color: $text-muted; margin-top: 1; }
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
        *(
            Binding(key, f"move('{status}')", verb, show=status in ("working", "done"))
            for key, status, verb in MOVES
        ),
        Binding("r", "reload", "Reload", show=False),
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

    def reload(self, select: str | None = None) -> None:
        """Redraw from disk, highlighting task `select` (if given) or the first task."""
        tasks = storage.load()
        self.query_one("#summary", Static).update(_summary(tasks))
        board = self.query_one("#board", OptionList)
        options, first_task = _board_options(tasks)
        index = next((i for i, o in enumerate(options) if select and o.id == select), first_task)
        board.clear_options()
        board.add_options(options)
        board.focus()
        if index is not None:
            # After the refresh, or the list overwrites the highlight and the
            # first Enter lands on nothing.
            self.call_after_refresh(setattr, board, "highlighted", index)

    def move(self, task_id: str, status: str) -> None:
        task = storage.get(task_id)
        if task and storage.set_status(task_id, status):
            icon, label, _ = STATUS[status]
            self.notify(f"{task['title']}  →  {icon} {label}", markup=False)
        self.reload(select=task_id)  # the highlight follows the task to its new group

    def action_move(self, status: str) -> None:
        board = self.query_one("#board", OptionList)
        if board.highlighted is not None:
            task_id = board.get_option_at_index(board.highlighted).id
            if task_id:
                self.move(task_id, status)

    def action_reload(self) -> None:
        self.reload()

    def action_add(self) -> None:
        self.app.push_screen(AddScreen(), callback=lambda task: self.reload(task and task["id"]))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        task = storage.get(event.option_id or "")
        if not task:
            return

        def picked(status: str | None) -> None:
            if status:
                self.move(task["id"], status)

        self.app.push_screen(StatusPicker(task), callback=picked)


class StatusPicker(ModalScreen[str | None]):
    """Enter on a task: pick its new status with ↑↓ + enter, or its key."""

    BINDINGS = [
        Binding("escape", "pick", "Cancel"),
        *(Binding(key, f"pick('{status}')", show=False) for key, status, _ in MOVES),
    ]

    def __init__(self, task: dict) -> None:
        super().__init__()
        self.task_data = task

    def compose(self) -> ComposeResult:
        current = self.task_data["status"]
        options = []
        for key, status, _ in MOVES:
            icon, label, color = STATUS[status]
            now = "  [dim]← now[/]" if status == current else ""
            options.append(Option(f"[bold $accent]{key}[/]   [{color}]{icon}  {label}[/]{now}", id=status))
        with Vertical(id="picker"):
            yield Static(self.task_data["title"], id="picker-title", markup=False)
            yield OptionList(*options, id="moves")
            yield Static("↑↓ enter to pick · or press a key · esc to cancel", classes="hint")
        yield Footer()

    def on_mount(self) -> None:
        moves = self.query_one("#moves", OptionList)
        moves.highlighted = [status for _, status, _ in MOVES].index(self.task_data["status"])

    def action_pick(self, status: str | None = None) -> None:
        self.dismiss(status)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option_id)


class AddScreen(ModalScreen[dict | None]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(id="add-box"):
            yield Label("New task")
            yield Input(placeholder="What are you working on?", id="task_title")
            yield Static("enter to save · esc to cancel", classes="hint")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#task_title", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        title = event.value.strip()
        if not title:
            self.notify("Type a title first.", severity="warning")
            return
        self.dismiss(storage.add(title))


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
