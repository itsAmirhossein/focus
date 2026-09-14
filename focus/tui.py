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

# status -> (icon, label, color), in board column order, left to right.
# Theme variables keep the colors legible in every theme.
STATUS = {
    "todo": ("○", "To do", "$text-muted"),
    "working": ("●", "Working", "$warning"),
    "review": ("◆", "In review", "$primary"),
    "blocked": ("■", "Blocked", "$error"),
    "done": ("✓", "Done", "$success"),
}

# One key per status, shared by the board and the picker so they never disagree.
MOVES = (
    ("s", "working", "Start"),
    ("v", "review", "Review"),
    ("b", "blocked", "Block"),
    ("t", "todo", "To do"),
    ("d", "done", "Done"),
)

CSS = """
#columns { height: 1fr; padding: 1 0 0 1; }
.column, .column:focus {
    width: 1fr;
    height: 1fr;
    max-height: 100%;
    margin-right: 1;
    padding: 0 1;
    border: round $panel-lighten-2;
    border-title-align: left;
    background: $background;
}
.column:focus { border: round $accent; }
/* Only the focused column shows its cursor; in the others it is just noise. */
.column > .option-list--option-highlighted {
    background: $background;
    color: $foreground;
    text-style: none;
}
.column:focus > .option-list--option-highlighted {
    background: $block-cursor-background;
    color: $block-cursor-foreground;
    text-style: $block-cursor-text-style;
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
    title = escape(task["title"])
    if task["status"] == "done":
        title = f"[dim strike]{title}[/]"
    return Option(title, id=task["id"])


def _column_options(tasks: list[dict]) -> list[Option | None]:
    """A column's tasks with a divider between each; dividers take no index."""
    options: list[Option | None] = []
    for task in tasks:
        if options:
            options.append(None)
        options.append(_task_option(task))
    return options


class Board(Screen):
    BINDINGS = [
        Binding("a", "add", "Add"),
        # priority: the focused OptionList would otherwise eat ←→ as horizontal scroll.
        Binding("left", "column(-1)", "Column", key_display="←→", priority=True),
        Binding("right", "column(1)", "Column", show=False, priority=True),
        *(
            Binding(key, f"move('{status}')", verb, show=status in ("working", "done"))
            for key, status, verb in MOVES
        ),
        Binding("r", "reload", "Reload", show=False),
        # "app." prefix required: action_quit lives on App, not on this screen.
        Binding("q", "app.quit", "Quit"),
    ]
    # reload() picks the starting column; the default would focus To do after it.
    AUTO_FOCUS = ""

    def compose(self) -> ComposeResult:
        with Horizontal(id="columns"):
            for status in STATUS:
                yield OptionList(id=f"col-{status}", classes="column")
        yield Footer()

    def on_mount(self) -> None:
        self.reload()

    def reload(self, select: str | None = None) -> None:
        """Redraw from disk. Focus follows task `select` if given, else stays put."""
        tasks = storage.load()
        target = None
        for status, (icon, label, color) in STATUS.items():
            column = self.query_one(f"#col-{status}", OptionList)
            group = [t for t in tasks if t["status"] == status]
            column.border_title = f"[bold {color}]{icon} {label.upper()}[/]  [dim]{len(group)}[/]"
            index = next((i for i, t in enumerate(group) if t["id"] == select), None)
            if index is not None:
                target = column
            elif group:
                index = min(column.highlighted or 0, len(group) - 1)  # keep the cursor's row
            column.clear_options()
            column.add_options(_column_options(group))
            if index is not None:
                # After the refresh, or the list overwrites the highlight.
                self.call_after_refresh(setattr, column, "highlighted", index)
        if not tasks:
            hint = Option("[dim]No tasks yet.\nPress [bold]a[/] to add one.[/]", disabled=True)
            self.query_one("#col-todo", OptionList).add_option(hint)
        if target is None and not isinstance(self.focused, OptionList):
            # First open: start where the work is.
            statuses = {t["status"] for t in tasks}
            start = "working" if "working" in statuses else next((s for s in STATUS if s in statuses), "todo")
            target = self.query_one(f"#col-{start}", OptionList)
        if target is not None:
            target.focus()

    def move(self, task_id: str, status: str) -> None:
        task = storage.get(task_id)
        if task and storage.set_status(task_id, status):
            icon, label, _ = STATUS[status]
            self.notify(f"{task['title']}  →  {icon} {label}", markup=False)
        self.reload(select=task_id)  # focus follows the task to its new column

    def action_column(self, step: int) -> None:
        columns = list(self.query(".column"))
        index = columns.index(self.focused) if self.focused in columns else 0
        columns[max(0, min(len(columns) - 1, index + step))].focus()

    def action_move(self, status: str) -> None:
        column = self.focused
        if isinstance(column, OptionList) and column.highlighted is not None:
            task_id = column.get_option_at_index(column.highlighted).id
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
