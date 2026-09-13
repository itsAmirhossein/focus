# focus

A minimal terminal workboard. When you are juggling several tasks across terminal
tabs and Claude Code sessions and lose the thread, type `focus` and see what you
were doing.

![The focus dashboard, with tasks grouped by status](docs/dashboard.png)

A task is a title and one of six statuses (`TODO`, `WORKING`, `SELF-REVIEW`,
`REVIEW`, `BLOCKED`, `DONE`). Nothing else — no IDs, links, owners, priorities,
deadlines, tags, or time tracking.

## Install

```bash
pipx install .
```

`focus` then works from any directory. Requires Python 3.10+. Built and tested on
macOS.

## Use

```bash
focus                    # open the dashboard
focus add                # add a task (form)
focus add Fix login      # add a task (no form)
focus start login        # ✓ Fix login → WORKING
focus self-review login
focus review login
focus done login
focus block login
```

Status commands take any unique part of a task's title, case-insensitive. If it
matches more than one task, focus lists them and changes nothing.

On the dashboard: `↑↓` navigate · `Enter` open · `a` add · `r` reload · `q` quit.

### Task detail

`Enter` on a task opens it. Every status is one keystroke away.

![Task detail, showing status and the action buttons](docs/detail.png)

`s` start · `f` self-review · `v` review · `d` done · `b` block · `esc` back.
The buttons are clickable too.

### Adding a task

`a` on the dashboard, or `focus add` from the shell. Type a title, press
`Enter`. New tasks start as `TODO`; `esc` cancels.

![The add-task form](docs/add.png)

## Themes

`ctrl+p` opens the command palette, where *Change theme* previews any of Textual's
themes for the current session. To keep one, set `FOCUS_THEME` in your shell
profile:

```bash
export FOCUS_THEME=nord
```

| `nord` | `gruvbox` |
| :--- | :--- |
| ![](docs/theme-nord.png) | ![](docs/theme-gruvbox.png) |

| `tokyo-night` | `catppuccin-latte` |
| :--- | :--- |
| ![](docs/theme-tokyo-night.png) | ![](docs/theme-catppuccin-latte.png) |

Any Textual theme name works — `dracula`, `monokai`, `solarized-light`,
`rose-pine`, `flexoki`, and the rest. An unknown name is ignored.

## Data

Tasks live in `~/.focus/tasks.json`, created on first write:

```json
[
  {
    "id": "3",
    "title": "Loading studies takes 8s on cold start",
    "status": "working"
  }
]
```

Edit it by hand if you like. `id` is focus's internal key — leave it out on new
rows and one is assigned. Fields from older versions (`owner`, `url`, `mr_url`)
are dropped the next time focus saves. A file that cannot be parsed is moved aside to
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

## License

MIT — see [LICENSE](LICENSE).
