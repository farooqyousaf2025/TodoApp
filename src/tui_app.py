# src/tui_app.py
"""Mouse-driven Textual front-end for the same TodoList model used by the CLI."""

from __future__ import annotations

from datetime import date
from typing import Iterable

from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, ProgressBar, Select, Static

from src.todo import VIEWS, Priority, Task, TodoList, parse_due

VIEW_LABELS = {
    "all": "Everything",
    "open": "Open only",
    "done": "Completed only",
    "overdue": "Overdue only",
    "high": "High priority only",
}

PRIORITY_COLOURS = {"HIGH": "bold red", "MEDIUM": "yellow", "LOW": "dim"}


def describe_due(task: Task, today: date) -> Text:
    if task.due is None:
        return Text("-", style="dim")
    days = (task.due - today).days
    if task.completed:
        return Text(task.due.strftime("%d %b"), style="dim")
    if days < 0:
        return Text(f"OVERDUE {-days}d", style="bold red")
    if days == 0:
        return Text("DUE TODAY", style="bold yellow")
    if days == 1:
        return Text("DUE TOMORROW", style="yellow")
    return Text(f"due in {days}d", style="green" if days > 3 else "cyan")


class TaskFormScreen(ModalScreen[dict | None]):
    """Shared dialog for creating and editing a task."""

    DEFAULT_CSS = """
    TaskFormScreen {
        align: center middle;
    }
    TaskFormScreen > Vertical {
        width: 74;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: thick $accent;
    }
    #form_error {
        color: $error;
        height: auto;
        min-height: 1;
    }
    #form_buttons {
        height: 3;
        margin-top: 1;
        align-horizontal: right;
    }
    Label {
        margin-top: 1;
    }
    """

    def __init__(self, task: Task | None, today: date) -> None:
        super().__init__()
        # 'task' is a read-only Screen property, so the edited task lives in .edited
        self.edited = task
        self.today = today

    def compose(self) -> ComposeResult:
        editing = self.edited is not None
        with Vertical():
            yield Static(f"{'Edit' if editing else 'Create'} task", id="form_title")
            yield Static("", id="form_error")
            yield Label("Description")
            yield Input(
                placeholder="What needs doing?",
                value=self.edited.description if editing else "",
                id="field_description",
            )
            yield Label("Priority")
            yield Select(
                [(label, priority) for label, priority in self.priority_options()],
                value=self.edited.priority if editing else Priority.MEDIUM,
                allow_blank=False,
                id="field_priority",
            )
            yield Label("Due date  (2026-10-31, +5, tomorrow, - for none)")
            yield Input(
                placeholder="no date",
                value=self.edited.due.isoformat() if editing and self.edited.due else "",
                id="field_due",
            )
            yield Label("Notes")
            yield Input(
                placeholder="optional",
                value=self.edited.notes if editing else "",
                id="field_notes",
            )
            with Horizontal(id="form_buttons"):
                yield Button("Save", variant="success", id="btn_save")
                yield Button("Cancel", variant="default", id="btn_cancel")

    @staticmethod
    def priority_options() -> Iterable[tuple[str, Priority]]:
        return [(priority.label, priority) for priority in Priority]

    def on_mount(self) -> None:
        self.query_one("#field_description", Input).focus()

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            event.stop()
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_save":
            self.submit()
        else:
            self.dismiss(None)

    def submit(self) -> None:
        description = self.query_one("#field_description", Input).value.strip()
        due_text = self.query_one("#field_due", Input).value.strip()
        error = self.query_one("#form_error", Static)
        if not description:
            error.update("A task needs a description.")
            return
        try:
            due = parse_due(due_text, self.today)
        except ValueError as problem:
            error.update(str(problem))
            return
        self.dismiss(
            {
                "description": description,
                "priority": self.query_one("#field_priority", Select).value,
                "due": due,
                "notes": self.query_one("#field_notes", Input).value.strip(),
            }
        )


class ConfirmScreen(ModalScreen[bool]):
    DEFAULT_CSS = """
    ConfirmScreen {
        align: center middle;
    }
    ConfirmScreen > Vertical {
        width: 60;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: thick $warning;
    }
    #confirm_buttons {
        height: 3;
        margin-top: 1;
        align-horizontal: right;
    }
    """

    def __init__(self, question: str) -> None:
        super().__init__()
        self.question = question

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self.question, id="confirm_text")
            with Horizontal(id="confirm_buttons"):
                yield Button("Yes", variant="error", id="btn_yes")
                yield Button("No", variant="default", id="btn_no")

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            event.stop()
            self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn_yes")


class TodoTUI(App):
    """Interactive terminal to-do list."""

    ENABLE_COMMAND_PALETTE = False

    CSS = """
    #toolbar {
        height: 3;
        margin: 0 1;
        align-horizontal: center;
    }
    #summary {
        height: 1;
        margin: 0 1;
    }
    #progress {
        margin: 0 1;
        height: 1;
    }
    #search {
        margin: 0 1;
    }
    #empty_hint {
        margin: 0 1;
        height: 1;
        color: $text-muted;
        text-style: italic;
    }
    DataTable {
        margin: 0 1;
        border: round $primary;
    }
    """

    BINDINGS = [
        ("a", "add", "Add"),
        ("e", "edit", "Edit"),
        ("space", "toggle", "Toggle done"),
        ("d", "delete", "Delete"),
        ("f", "next_view", "Filter"),
        ("ctrl+l", "clear_done", "Clear completed"),
        ("s", "focus_search", "Search"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, filename: str = "tasks.json") -> None:
        super().__init__()
        self.todo = TodoList(filename)
        self.view = "all"
        self.query_text = ""
        self.shown: list[Task] = []
        self.today = date.today()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="toolbar"):
            yield Button("Add", variant="primary", id="btn_add")
            yield Button("Edit", id="btn_edit")
            yield Button("Toggle", variant="success", id="btn_toggle")
            yield Button("Delete", variant="error", id="btn_delete")
            yield Select(
                [(VIEW_LABELS[name], name) for name in VIEWS],
                value="all",
                allow_blank=False,
                id="view_select",
            )
        yield Static("", id="summary")
        yield ProgressBar(total=100, show_percentage=True, id="progress")
        yield Input(placeholder="Search descriptions and notes... (s)", id="search")
        yield Static("Nothing matches this view.", id="empty_hint")
        yield DataTable(cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Status", "P", "Task", "Due", "Notes")
        table.focus()
        self.refresh_table()

    # ---------- data ----------
    def refresh_table(self) -> None:
        self.today = date.today()
        table = self.query_one(DataTable)
        had_rows = table.row_count > 0
        was_first = had_rows and table.cursor_coordinate.row == 0
        table.clear()
        self.shown = self.todo.visible(self.view, self.query_text, self.today)
        for task in self.shown:
            # Rows are keyed by index, so numbers and clicks always map back to the model.
            index = self.todo.tasks.index(task)
            table.add_row(*self.cells_for(task), key=str(index))
        if was_first and self.shown:
            table.move_cursor(row=0)
        self.query_one("#empty_hint", Static).display = not self.shown
        self.update_summary()

    def cells_for(self, task: Task) -> list[Text]:
        if task.completed:
            status, style = "done", "green"
            description = Text(task.description, style="strike dim")
        else:
            status, style = "open", "cyan"
            description = Text(task.description, style="bold")
        return [
            Text(status, style=style),
            Text(task.priority.name[0], style=PRIORITY_COLOURS[task.priority.name]),
            description,
            describe_due(task, self.today),
            Text(task.notes[:28] or "-", style="dim"),
        ]

    def update_summary(self) -> None:
        counts = self.todo.counts(self.today)
        self.query_one("#summary", Static).update(
            f"Total [bold]{counts['total']}[/bold]  ·  Open [cyan]{counts['open']}[/]  ·  "
            f"Done [green]{counts['done']}[/]  ·  Overdue [red]{counts['overdue']}[/]  ·  "
            f"High priority [yellow]{counts['high']}[/]  ·  View: {VIEW_LABELS[self.view]}"
        )
        progress = self.query_one(ProgressBar)
        progress.update(total=max(1, counts["total"]), progress=counts["done"])

    def selected_task(self) -> Task | None:
        table = self.query_one(DataTable)
        if not self.shown:
            return None
        row = table.cursor_coordinate.row
        if not 0 <= row < len(self.shown):
            return None
        return self.shown[row]

    # ---------- actions ----------
    def action_add(self) -> None:
        self.push_screen(TaskFormScreen(None, self.today), self.apply_form)

    def action_edit(self) -> None:
        task = self.selected_task()
        if task is None:
            self.notify("Select a task first.", severity="warning")
            return
        self.push_screen(TaskFormScreen(task, self.today), lambda values: self.apply_form(values, task))

    def apply_form(self, values: dict | None, task: Task | None = None) -> None:
        if values is None:
            return
        if task is None:
            created = self.todo.add_task(
                values["description"], values["priority"], values["due"], values["notes"]
            )
            self.notify(f"Added: {created.description}")
        else:
            task.description = values["description"]
            task.priority = values["priority"]
            task.due = values["due"]
            task.notes = values["notes"]
            self.todo.save_tasks()
            self.notify(f"Updated: {task.description}")
        self.refresh_table()

    def action_toggle(self) -> None:
        task = self.selected_task()
        if task is None:
            self.notify("Select a task first.", severity="warning")
            return
        now_done = task.toggle()
        self.todo.save_tasks()
        self.refresh_table()
        self.notify(f"{'Completed' if now_done else 'Reopened'}: {task.description}")

    def action_delete(self) -> None:
        task = self.selected_task()
        if task is None:
            self.notify("Select a task first.", severity="warning")
            return
        def perform(confirmed: bool) -> None:
            if not confirmed:
                return
            self.todo.remove_task(task)
            self.refresh_table()
            self.notify(f"Removed: {task.description}", severity="warning")

        self.push_screen(ConfirmScreen(f"Delete '{task.description}'?"), perform)

    def action_clear_done(self) -> None:
        done = sum(1 for task in self.todo.tasks if task.completed)
        if not done:
            self.notify("No completed tasks.", severity="warning")
            return
        def perform(confirmed: bool) -> None:
            if confirmed:
                self.todo.clear_completed()
                self.refresh_table()
                self.notify(f"Cleared {done} completed task(s).")

        self.push_screen(ConfirmScreen(f"Delete {done} completed task(s)?"), perform)

    def action_next_view(self) -> None:
        self.view = VIEWS[(VIEWS.index(self.view) + 1) % len(VIEWS)]
        self.query_one("#view_select", Select).value = self.view
        self.refresh_table()

    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    # ---------- widget events ----------
    def on_button_pressed(self, event: Button.Pressed) -> None:
        # Modal buttons bubble up here too, so unknown ids must be ignored.
        action = {
            "btn_add": self.action_add,
            "btn_edit": self.action_edit,
            "btn_toggle": self.action_toggle,
            "btn_delete": self.action_delete,
        }.get(event.button.id)
        if action is not None:
            action()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "view_select" and event.value in VIEWS:
            self.view = str(event.value)
            self.refresh_table()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search":
            self.query_text = event.value
            self.refresh_table()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_toggle()


def main() -> None:
    import sys

    TodoTUI(sys.argv[1] if len(sys.argv) > 1 else "tasks.json").run()


if __name__ == "__main__":
    main()
