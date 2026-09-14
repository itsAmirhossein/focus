"""Command line entry point."""

from __future__ import annotations

import sys

from . import storage

STATUS_COMMANDS = {
    "start": "working",
    "review": "review",
    "done": "done",
    "block": "blocked",
}

HELP = """focus — minimal terminal workboard

  focus                                open the board
  focus add [title]                    add a task
  focus start <title>                  → WORKING
  focus review <title>                 → REVIEW
  focus done <title>                   → DONE
  focus block <title> [--why <reason>] → BLOCKED
  focus rename <title> --to <title>    change a title
  focus delete <title>                 remove a task

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


def _split(args: list[str], flag: str) -> tuple[str, str]:
    """Words before `flag` and words after it: [a, --to, b, c] -> ("a", "b c")."""
    cut = args.index(flag) if flag in args else len(args)
    return " ".join(args[:cut]).strip(), " ".join(args[cut + 1 :]).strip()


def _find_one(query: str) -> dict | None:
    """The single task matching `query`; otherwise say why and return None."""
    matches = storage.find(query)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        print(f"✗ No task matches “{query}”.", file=sys.stderr)
    else:
        print(f"✗ “{query}” matches {len(matches)} tasks, be more specific:", file=sys.stderr)
        for task in matches:
            print(f"    {task['title']}", file=sys.stderr)
    return None


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
        query, reason = _split(rest, "--why")
        if not query:
            print(f"usage: focus {command} <title>", file=sys.stderr)
            return 2
        task = _find_one(query)
        if not task:
            return 1
        status = STATUS_COMMANDS[command]
        reason = reason or task["reason"]  # re-blocking without --why keeps the old reason
        storage.set_status(task["id"], status, reason)
        note = f" ({reason})" if status == "blocked" and reason else ""
        print(f"✓ {task['title']} → {status.upper()}{note}")
        return 0

    if command == "rename":
        query, title = _split(rest, "--to")
        if not query or not title:
            print("usage: focus rename <title> --to <new title>", file=sys.stderr)
            return 2
        task = _find_one(query)
        if not task:
            return 1
        storage.rename(task["id"], title)
        print(f"✓ {task['title']} → {title}")
        return 0

    if command == "delete":
        query = " ".join(rest).strip()
        if not query:
            print("usage: focus delete <title>", file=sys.stderr)
            return 2
        task = _find_one(query)
        if not task:
            return 1
        storage.delete(task["id"])
        print(f"✓ Deleted: {task['title']}")
        return 0

    print(f"✗ Unknown command: {command}\n", file=sys.stderr)
    print(HELP, file=sys.stderr)
    return 2
