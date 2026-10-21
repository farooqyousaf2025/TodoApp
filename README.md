# To-Do List App

A to-do application in Python with OOP principles and **two** terminal interfaces that share
the same model and the same JSON file:

- a plain CLI built only with the standard library
- a mouse-driven Textual TUI with a table, dialogs and keyboard shortcuts

## Features
- **Add tasks** with an optional priority (low / medium / high), due date and notes
- **Done / undone** toggle - completed tasks are struck through
- **Edit** any field of an existing task
- **Remove** tasks (with confirmation) and **clear all completed** at once
- **Filter views**: everything, open, completed, overdue, high priority
- **Search** across descriptions and notes
- **Statistics** with a completion progress bar
- **Auto-save** after every change, written atomically so a crash cannot corrupt the file
- **Reads the old task file format** (tasks without priority, due date or notes still load)
- Safe input handling - a typo never crashes the app or loses what you typed

## Requirements
Python 3.9 or newer. The plain CLI needs nothing else. The Textual TUI needs:

```bash
python -m pip install -r requirements.txt
```

## Run
Start in the project folder (the folder that contains `src`):

```bash
python -m src.main                 # plain CLI, uses tasks.json
python -m src.main work.json       # plain CLI, another file
python -m src.tui_app              # Textual TUI, uses tasks.json
python -m src.tui_app work.json    # Textual TUI, another file
```

### Textual TUI
Click anywhere: table rows, toolbar buttons, the filter dropdown. Or use the keyboard:

| Key | Action | Key | Action |
| --- | --- | --- | --- |
| `a` | add task | `e` | edit selected task |
| `space` / click | toggle done | `d` | delete (asks first) |
| `f` | next filter view | `s` | jump to search box |
| `Ctrl+L` | clear completed | `q` | quit |

In a dialog, `Enter` saves and `Escape` cancels. A wrong due date or priority keeps the dialog
open and tells you what to fix instead of discarding your text.

### Plain CLI menu
```
 1  list        2  add            3  done / undone
 4  edit        5  remove         6  filter
 7  search      8  clear done     9  stats
 0  quit
```
The CLI styles the terminal itself with ANSI escapes, so it also works where Textual is not
installed (it falls back to plain colour-free text, and to ASCII boxes on very old consoles).

## Due date formats
`2026-10-31`, `31/10/2026`, `+5` (days from today), `today`, `tomorrow`, or `-` for no date.

## Tests
```bash
python -m unittest discover -s tests
```
`tests/test_todo.py` covers the model and the input prompts; `tests/test_tui.py` drives the
Textual app headlessly (clicks, keys, dialogs) with Textual's own test pilot.

## Structure
- `src/todo.py` - `Task`, `Priority` and `TodoList` model plus JSON storage
- `src/style.py` - ANSI colours, panels and rows for the plain CLI
- `src/main.py` - plain CLI menu loop
- `src/tui_app.py` - Textual application, table, dialogs
- `tests/` - unit tests for the model and the TUI
