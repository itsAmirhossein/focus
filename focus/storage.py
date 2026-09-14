"""JSON storage. The only module that knows where tasks live or how they are shaped."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

STATUSES = ("todo", "working", "review", "blocked", "done")

HOME = Path(os.environ.get("FOCUS_HOME") or Path.home() / ".focus")
DATA_FILE = HOME / "tasks.json"


def _clean(task: dict) -> dict:
    """Coerce a raw dict into the task shape; junk values fall back to defaults."""
    status = task.get("status")
    if status == "self-review":  # retired status; those tasks were still in progress
        status = "working"
    return {
        "id": str(task.get("id") or "").strip(),
        "title": str(task.get("title") or "").strip(),
        "status": status if status in STATUSES else "todo",
        "reason": str(task.get("reason") or "").strip(),
    }


def _next_id(tasks: list[dict]) -> int:
    return max((int(t["id"]) for t in tasks if t["id"].isdecimal()), default=0) + 1


def load() -> list[dict]:
    """Read tasks. Missing file -> []. Unreadable content -> quarantined, then []."""
    try:
        raw = json.loads(DATA_FILE.read_text())
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        raw = None
    if not isinstance(raw, list):
        # Keep the user's file instead of overwriting it on the next save.
        DATA_FILE.replace(DATA_FILE.with_name("tasks.json.corrupt"))
        return []
    tasks = [_clean(item) for item in raw if isinstance(item, dict)]
    tasks = [t for t in tasks if t["title"]]
    next_id, seen = _next_id(tasks), set()
    for task in tasks:
        # Ids are internal; a hand-added or copy-pasted row just gets a fresh one.
        if not task["id"] or task["id"] in seen:
            task["id"] = str(next_id)
            next_id += 1
        seen.add(task["id"])
    return tasks


def save(tasks: list[dict]) -> None:
    """Write tasks atomically, so a crash mid-write cannot truncate the file."""
    HOME.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=HOME, suffix=".tmp")
    with os.fdopen(fd, "w") as handle:
        json.dump(tasks, handle, indent=2, ensure_ascii=False)
    os.replace(tmp, DATA_FILE)


def get(task_id: str) -> dict | None:
    return next((t for t in load() if t["id"] == task_id), None)


def find(query: str) -> list[dict]:
    """Tasks titled exactly `query`, else those whose title contains it (any case)."""
    query = query.strip().lower()
    tasks = load()
    exact = [t for t in tasks if t["title"].lower() == query]
    return exact or [t for t in tasks if query in t["title"].lower()]


def add(title: str) -> dict:
    """Add a TODO task and return it."""
    tasks = load()
    task = _clean({"id": _next_id(tasks), "title": title})
    tasks.append(task)
    save(tasks)
    return task


def _update(task_id: str, **fields) -> bool:
    tasks = load()
    for task in tasks:
        if task["id"] == task_id:
            task.update(fields)
            save(tasks)
            return True
    return False


def set_status(task_id: str, status: str, reason: str = "") -> bool:
    """Set a task's status; `reason` is kept only while blocked. False if the task does not exist."""
    return _update(task_id, status=status, reason=reason.strip() if status == "blocked" else "")


def rename(task_id: str, title: str) -> bool:
    """Change a task's title. False if the title is empty or the task does not exist."""
    return bool(title.strip()) and _update(task_id, title=title.strip())


def delete(task_id: str) -> bool:
    """Remove a task. False if the task does not exist."""
    tasks = load()
    kept = [t for t in tasks if t["id"] != task_id]
    if len(kept) == len(tasks):
        return False
    save(kept)
    return True
