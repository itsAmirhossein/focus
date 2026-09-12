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

  focus                    open the dashboard
  focus add                add a task
  focus start <id>         → WORKING
  focus self-review <id>   → SELF-REVIEW
  focus review <id>        → REVIEW
  focus done <id>          → DONE
  focus block <id>         → BLOCKED

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
        if _needs_terminal():
            return 2
        from .tui import run_add

        task = run_add()
        if task:
            print(f"✓ Task {task['id']} added")
            return 0
        print("✗ Cancelled.")
        return 1

    if command in STATUS_COMMANDS:
        if len(rest) != 1:
            print(f"usage: focus {command} <task_id>", file=sys.stderr)
            return 2
        task_id, status = rest[0], STATUS_COMMANDS[command]
        if storage.set_status(task_id, status):
            print(f"✓ {task_id} → {status.upper()}")
            return 0
        print(f"✗ Task {task_id} not found.", file=sys.stderr)
        return 1

    print(f"✗ Unknown command: {command}\n", file=sys.stderr)
    print(HELP, file=sys.stderr)
    return 2
