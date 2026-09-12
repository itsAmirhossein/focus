"""JSON storage. The only module that knows where tasks live or how they are shaped."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

STATUSES = ("todo", "working", "self-review", "review", "blocked", "done")
OWNERS = ("me", "claude")

HOME = Path(os.environ.get("FOCUS_HOME") or Path.home() / ".focus")
DATA_FILE = HOME / "tasks.json"


def _clean(task: dict) -> dict:
    """Coerce a raw dict into the task shape; junk values fall back to defaults."""
    return {
        "id": str(task.get("id", "")).strip(),
        "title": str(task.get("title") or "").strip() or "(untitled)",
        "status": task.get("status") if task.get("status") in STATUSES else "todo",
        "owner": task.get("owner") if task.get("owner") in OWNERS else "me",
        "url": str(task.get("url") or "").strip(),
        "mr_url": str(task.get("mr_url") or "").strip(),
    }


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
    tasks, seen = [], set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        task = _clean(item)
        if task["id"] and task["id"] not in seen:
            seen.add(task["id"])
            tasks.append(task)
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


def add(task: dict) -> bool:
    """Add a task. False if the id is already taken."""
    tasks = load()
    task = _clean(task)
    if any(t["id"] == task["id"] for t in tasks):
        return False
    tasks.append(task)
    save(tasks)
    return True


def set_status(task_id: str, status: str) -> bool:
    """Set a task's status. False if the task does not exist."""
    tasks = load()
    for task in tasks:
        if task["id"] == task_id:
            task["status"] = status
            save(tasks)
            return True
    return False
