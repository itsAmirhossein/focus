"""Command line entry point."""

from __future__ import annotations

import sys

from . import storage

STATUS_COMMANDS = {
    "start": "working",
    "self-review": "self-review",
    "review": "review",
    "done": "done",
    "block": "blocked",
}

HELP = """focus — minimal terminal workboard

  focus                       open the board
  focus add [title]           add a task
  focus start <title>         → WORKING
  focus self-review <title>   → SELF-REVIEW
  focus review <title>        → REVIEW
  focus done <title>          → DONE
  focus block <title>         → BLOCKED

<title> can be any unique part of the title, e.g. `focus done login`.
Tasks live in {path}
""".format(path=storage.DATA_FILE)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        return _run(args)
    except OSError as error:  # unreadable/unwritable ~/.focus
        print(f"✗ {error}", file=sys.stderr)
        return 1


def _needs_terminal() -> bool:
    """The TUI blocks forever without a tty, so refuse instead of hanging."""
    if sys.stdin.isatty() and sys.stdout.isatty():
        return False
    print("✗ focus needs an interactive terminal.", file=sys.stderr)
    return True


def _run(args: list[str]) -> int:
    if not args:
        if _needs_terminal():
            return 2
        from .tui import run_board

        run_board()
        return 0

    command, rest = args[0], args[1:]

    if command in ("help", "-h", "--help"):
        print(HELP)
        return 0

    if command == "add":
        title = " ".join(rest).strip()
        if title:
            task = storage.add(title)
        elif _needs_terminal():
            return 2
        else:
            from .tui import run_add

            task = run_add()
        if task:
            print(f"✓ Added: {task['title']}")
            return 0
        print("✗ Cancelled.")
        return 1

    if command in STATUS_COMMANDS:
        query = " ".join(rest).strip()
        if not query:
            print(f"usage: focus {command} <title>", file=sys.stderr)
            return 2
        matches = storage.find(query)
        if not matches:
            print(f"✗ No task matches “{query}”.", file=sys.stderr)
            return 1
        if len(matches) > 1:
            print(f"✗ “{query}” matches {len(matches)} tasks, be more specific:", file=sys.stderr)
            for task in matches:
                print(f"    {task['title']}", file=sys.stderr)
            return 1
        task, status = matches[0], STATUS_COMMANDS[command]
        storage.set_status(task["id"], status)
        print(f"✓ {task['title']} → {status.upper()}")
        return 0

    print(f"✗ Unknown command: {command}\n", file=sys.stderr)
    print(HELP, file=sys.stderr)
    return 2
