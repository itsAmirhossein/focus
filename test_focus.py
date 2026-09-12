"""Self-check: python test_focus.py  (no framework, asserts only)."""

import asyncio
import io
import json
import os
import tempfile
from contextlib import redirect_stdout, redirect_stderr

os.environ["FOCUS_HOME"] = tempfile.mkdtemp()  # must precede the imports below

from focus import cli, storage  # noqa: E402
from focus.tui import AddScreen, Detail, _board_options  # noqa: E402


def run_cli(*args):
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(out):
        code = cli.main(list(args))
    return code, out.getvalue().strip()


def test_storage():
    assert storage.load() == [], "empty list when no file exists"

    assert storage.add({"id": "1", "title": "No links", "owner": "me"})
    assert not storage.add({"id": "1", "title": "Duplicate"}), "duplicate id rejected"
    assert storage.add(
        {
            "id": "2",
            "title": "With links",
            "owner": "claude",
            "url": "https://example.com/wp/2",
            "mr_url": "https://example.com/mr/2",
        }
    )

    tasks = storage.load()
    assert [t["id"] for t in tasks] == ["1", "2"]
    assert tasks[0]["status"] == "todo", "new tasks start as TODO"
    assert tasks[0]["url"] == "" and tasks[0]["mr_url"] == "", "links are optional"
    assert tasks[1]["owner"] == "claude"
    assert json.loads(storage.DATA_FILE.read_text())[1]["mr_url"].endswith("/mr/2")


def test_status_commands():
    for command, status in cli.STATUS_COMMANDS.items():
        code, out = run_cli(command, "1")
        assert code == 0 and out == f"✓ 1 → {status.upper()}", out
        assert storage.get("1")["status"] == status

    code, out = run_cli("done", "nope")
    assert code == 1 and out == "✗ Task nope not found.", out

    assert run_cli("start")[0] == 2, "missing id is a usage error"
    assert run_cli("frobnicate", "1")[0] == 2, "unknown command"
    assert run_cli("--help")[0] == 0


def test_malformed_json():
    storage.DATA_FILE.write_text("{ this is not valid json")
    assert storage.load() == [], "malformed file reads as empty"
    assert storage.DATA_FILE.with_name("tasks.json.corrupt").exists(), "bad file kept"

    storage.DATA_FILE.write_text('[{"id": 55, "status": "bogus", "owner": null}, "junk", {}]')
    tasks = storage.load()
    assert len(tasks) == 1, "junk rows dropped"
    assert tasks[0] == {
        "id": "55",
        "title": "(untitled)",
        "status": "todo",
        "owner": "me",
        "url": "",
        "mr_url": "",
    }, tasks


def test_grouping():
    def rows(options):
        return [o for o in options if o is not None]  # separators take no index

    options, first = _board_options(
        [
            {"id": "9", "title": "t", "status": "working", "owner": "me"},
            {"id": "8", "title": "t", "status": "done", "owner": "claude"},
        ]
    )
    assert rows(options)[first].id == "9", "first selectable row is the active task"
    assert [o.id for o in rows(options) if o.id] == ["9", "8"]

    # A task in a later group: the highlight must skip the empty groups' rows,
    # and the separators between them must not shift the index.
    options, first = _board_options([{"id": "7", "title": "t", "status": "done", "owner": "me"}])
    assert rows(options)[first].id == "7", rows(options)[first]
    assert not rows(options)[first].disabled, "highlight must land on a selectable row"

    options, first = _board_options([])
    assert first is None, "nothing to highlight on an empty board"


async def drive_tui():
    from focus.tui import BoardApp

    storage.save(
        [
            {"id": "100", "title": "Linked", "status": "working", "owner": "claude",
             "url": "https://example.com/wp/100", "mr_url": ""},
            {"id": "200", "title": "Bare", "status": "todo", "owner": "me",
             "url": "", "mr_url": ""},
        ]
    )
    opened = []
    import webbrowser

    webbrowser.open = lambda url: opened.append(url)

    app = BoardApp()
    async with app.run_test() as pilot:
        await pilot.pause()

        # Dashboard -> detail of the highlighted (first active) task.
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, Detail) and app.screen.task_id == "100"

        # Open task URL works; the MR button is disabled because there is no MR.
        await pilot.press("o")
        assert opened == ["https://example.com/wp/100"], opened
        assert app.screen.query_one("#open_mr").disabled
        assert not app.screen.query_one("#open_task").disabled

        # Status change returns to the dashboard.
        await pilot.press("d")
        await pilot.pause()
        assert storage.get("100")["status"] == "done"

        # Add a task through the modal.
        await pilot.press("a")
        await pilot.pause()
        assert isinstance(app.screen, AddScreen)
        await pilot.press(*"300")
        await pilot.press("tab")
        await pilot.press(*"New one")
        await pilot.press("ctrl+s")
        await pilot.pause()

        added = storage.get("300")
        assert added and added["title"] == "New one" and added["status"] == "todo", added

        # Add a second task, picking Claude as the owner from the keyboard.
        await pilot.press("a")
        await pilot.pause()
        await pilot.press(*"400")
        await pilot.press("tab")
        await pilot.press(*"Claude one")
        await pilot.press("tab")
        await pilot.press("down")
        await pilot.press("space")
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert storage.get("400")["owner"] == "claude", storage.get("400")
        assert storage.get("300")["owner"] == "me", "Me is the default owner"

        assert app.screen.query_one("#board").option_count > 0

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


for check in (test_storage, test_status_commands, test_malformed_json, test_grouping):
    check()
    print(f"✓ {check.__name__}")
asyncio.run(drive_tui())
print("✓ drive_tui")
asyncio.run(drive_theme())
print("✓ drive_theme")
print("\nall checks passed")
