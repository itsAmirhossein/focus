"""Self-check: python test_focus.py  (no framework, asserts only)."""

import asyncio
import io
import json
import os
import tempfile
from contextlib import redirect_stdout, redirect_stderr

os.environ["FOCUS_HOME"] = tempfile.mkdtemp()  # must precede the imports below

from focus import cli, storage  # noqa: E402
from focus.tui import AddScreen, Board, StatusPicker  # noqa: E402


def run_cli(*args):
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(out):
        code = cli.main(list(args))
    return code, out.getvalue().strip()


def test_storage():
    assert storage.load() == [], "empty list when no file exists"

    first = storage.add("Fix login")
    second = storage.add("Fix login redirect")
    assert (first["id"], second["id"]) == ("1", "2"), "ids are assigned in order"

    tasks = storage.load()
    assert tasks[0] == {"id": "1", "title": "Fix login", "status": "todo"}, tasks
    assert json.loads(storage.DATA_FILE.read_text())[1]["title"] == "Fix login redirect"

    assert [t["id"] for t in storage.find("REDIRECT")] == ["2"], "match ignores case"
    assert [t["id"] for t in storage.find("fix login")] == ["1"], "exact title wins"
    assert len(storage.find("fix")) == 2
    assert storage.find("nope") == []


def test_cli():
    for command, status in cli.STATUS_COMMANDS.items():
        code, out = run_cli(command, "fix", "login")  # words join, no quotes needed
        assert code == 0 and out == f"✓ Fix login → {status.upper()}", out
        assert storage.get("1")["status"] == status

    code, out = run_cli("done", "fix")
    assert code == 1 and "matches 2 tasks" in out and "Fix login redirect" in out, out
    code, out = run_cli("done", "nope")
    assert code == 1 and out == "✗ No task matches “nope”.", out

    code, out = run_cli("add", "Write", "docs")
    assert code == 0 and out == "✓ Added: Write docs", out
    assert storage.find("write docs")[0]["status"] == "todo"

    assert run_cli("start")[0] == 2, "missing title is a usage error"
    assert run_cli("frobnicate", "1")[0] == 2, "unknown command"
    assert run_cli("--help")[0] == 0


def test_malformed_json():
    storage.DATA_FILE.write_text("{ this is not valid json")
    assert storage.load() == [], "malformed file reads as empty"
    assert storage.DATA_FILE.with_name("tasks.json.corrupt").exists(), "bad file kept"

    storage.DATA_FILE.write_text(json.dumps([
        {"id": 55, "title": " Old ", "status": "bogus", "owner": "me", "url": "x"},
        {"title": "Hand-added"},
        {"id": 55, "title": "Copy-pasted"},
        {"id": 9, "title": "Retired status", "status": "self-review"},
        "junk",
        {},
    ]))
    tasks = storage.load()
    assert tasks == [
        {"id": "55", "title": "Old", "status": "todo"},
        {"id": "56", "title": "Hand-added", "status": "todo"},
        {"id": "57", "title": "Copy-pasted", "status": "todo"},
        {"id": "9", "title": "Retired status", "status": "working"},
    ], tasks


async def drive_tui():
    from focus.tui import BoardApp

    storage.save(
        [
            {"id": "100", "title": "Active one", "status": "working"},
            # Brackets must render as text, not crash as markup.
            {"id": "200", "title": "Fix [urgent] bug", "status": "todo"},
        ]
    )

    def focused_column():
        return app.screen.focused.id

    def highlighted_id():
        column = app.screen.focused
        return column.get_option_at_index(column.highlighted).id

    app = BoardApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()

        # The board opens on the Working column, where the work is.
        assert focused_column() == "col-working" and highlighted_id() == "100"

        # Enter opens the picker with the current status highlighted: down + enter
        # moves "working" one step, to review.
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, StatusPicker), app.screen
        await pilot.press("down", "enter")
        await pilot.pause()
        assert isinstance(app.screen, Board)
        assert storage.get("100")["status"] == "review"

        # Escape cancels; a key in the picker moves directly.
        await pilot.press("enter", "escape")
        await pilot.pause()
        assert isinstance(app.screen, Board) and storage.get("100")["status"] == "review"
        await pilot.press("enter", "b")
        await pilot.pause()
        assert storage.get("100")["status"] == "blocked"

        # Hotkeys work straight from the board, and focus follows the task's column.
        assert focused_column() == "col-blocked" and highlighted_id() == "100"
        await pilot.press("d")
        await pilot.pause()
        assert storage.get("100")["status"] == "done"
        assert focused_column() == "col-done" and highlighted_id() == "100"

        # Add a task through the modal; Enter saves and highlights it.
        await pilot.press("a")
        await pilot.pause()
        assert isinstance(app.screen, AddScreen)
        await pilot.press(*"New one", "enter")
        await pilot.pause()
        added = storage.find("new one")
        assert added and added[0]["status"] == "todo", added
        assert focused_column() == "col-todo" and highlighted_id() == added[0]["id"]

        # ←→ switch columns and stop at the edges.
        await pilot.press("right")
        assert focused_column() == "col-working"
        await pilot.press("left", "left")
        assert focused_column() == "col-todo"

        # Empty title is refused, escape cancels.
        await pilot.press("a")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, AddScreen), "empty title must not save"
        await pilot.press("escape")
        await pilot.pause()
        assert len(storage.load()) == 3

        assert app.screen.query_one("#col-todo").option_count == 2

        # q quits from the dashboard (needs the app.quit namespace, not quit).
        await pilot.press("q")
        await pilot.pause()
        assert not app.is_running, "q must exit the app"


async def drive_theme():
    from focus.tui import BoardApp

    os.environ["FOCUS_THEME"] = "nord"
    app = BoardApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.theme == "nord", app.theme

    os.environ["FOCUS_THEME"] = "not-a-theme"
    app = BoardApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.theme != "not-a-theme", "an unknown theme must not be applied"
    del os.environ["FOCUS_THEME"]


for check in (test_storage, test_cli, test_malformed_json):
    check()
    print(f"✓ {check.__name__}")
asyncio.run(drive_tui())
print("✓ drive_tui")
asyncio.run(drive_theme())
print("✓ drive_theme")
print("\nall checks passed")
