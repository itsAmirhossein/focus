# focus

A minimal terminal workboard. When you are juggling several tasks across terminal
tabs and Claude Code sessions and lose the thread, type `focus` and see what you
were doing.

```
╭────────────────────────────────────────────────╮
│                  MY FOCUS                      │
╰────────────────────────────────────────────────╯

ACTIVE

  14718  Loading Studies
         🟡 WORKING       🤖 Claude

  14725  WebView Permission
         🟣 SELF-REVIEW   👨‍💻 Me

REVIEW

  14712  Scroll bar
         🔵 REVIEW        🤖 Claude
```

Six statuses (`TODO`, `WORKING`, `SELF-REVIEW`, `REVIEW`, `BLOCKED`, `DONE`), two
owners (Me, Claude), an optional task URL and MR URL. Nothing else — no
priorities, deadlines, tags, or time tracking.

## Install

```bash
pipx install .
```

`focus` then works from any directory. Requires Python 3.10+. Built and tested on
macOS.

## Use

```bash
focus                    # open the dashboard
focus add                # add a task
focus start 14718        # ✓ 14718 → WORKING
focus self-review 14718
focus review 14718
focus done 14718
focus block 14718
```

**Dashboard:** `↑↓` navigate · `Enter` open · `a` add · `r` reload · `q` quit.

**Task detail:** `o` open task URL · `m` open MR URL · `s` start · `f` self-review ·
`v` review · `d` done · `b` block · `esc` back. Buttons are clickable too.

## Data

Tasks live in `~/.focus/tasks.json`, created on first write:

```json
[
  {
    "id": "14718",
    "title": "Loading Studies",
    "status": "working",
    "owner": "claude",
    "url": "https://openproject.example.com/work_packages/14718",
    "mr_url": "https://gitlab.example.com/project/merge_requests/123"
  }
]
```

Edit it by hand if you like. A file that cannot be parsed is moved aside to
`tasks.json.corrupt` rather than overwritten. Set `FOCUS_HOME` to keep the data
somewhere else.

## Tests

```bash
python -m venv .venv && .venv/bin/pip install textual
.venv/bin/python test_focus.py
```

## Limitations

- No delete or edit command — fix mistakes in `tasks.json`.
- Last writer wins; two dashboards open at once can clobber each other's status
  change. Press `r` to reload.
