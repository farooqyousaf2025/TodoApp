# src/main.py
"""Interactive command-line UI for the to-do list."""

from __future__ import annotations

import os
import sys
from datetime import date

from src import style
from src.todo import VIEWS, Priority, TodoList, parse_due

if sys.platform == "win32":
    # Without this, cmd.exe prints ANSI escapes as raw characters.
    os.system("")

VIEW_LABELS = {
    "all": "everything",
    "open": "open tasks only",
    "done": "completed only",
    "overdue": "overdue only",
    "high": "high priority only",
}

# Returned by any prompt the user closed with Ctrl-C / Ctrl-Z so the loop can stop.
QUIT = object()


def ask(prompt: str) -> str | None:
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        return None


class App:
    def __init__(self, filename: str = "tasks.json"):
        self.todo = TodoList(filename)
        self.view = "all"
        self.query = ""
        self.shown: list = []
        if self.todo.tasks:
            self.status = (
                f"{len(self.todo.tasks)} task(s) loaded from {os.path.basename(filename)}.",
                "info",
            )
        else:
            self.status = ("Press 2 to add your first task.", "info")
        self.today = date.today()

    # ---------- rendering ----------
    def draw(self) -> None:
        self.today = date.today()
        self.shown = self.todo.visible(self.view, self.query, self.today)
        counts = self.todo.counts(self.today)

        lines = style.banner(counts["total"], counts["done"], self._filter_label(), self.today)
        lines.append("")
        if self.shown:
            for index, task in enumerate(self.shown, start=1):
                lines.extend(style.task_row(index, task, self.today))
        else:
            lines.append(style.paint("   nothing to show", style.DIM, style.ITALIC))
        lines.append("")
        lines.append(style.message(*self.status))

        print(style.panel(" MY TASKS ", lines))
        print(style.menu())
        print(style.legend())

    def _filter_label(self) -> str:
        label = "" if self.view == "all" else VIEW_LABELS[self.view]
        if self.query:
            label = f"{label} matching '{self.query}'".strip()
        return label

    # ---------- helpers ----------
    def pick_number(self, prompt: str) -> object:
        if not self.shown:
            self.status = ("No tasks listed - add one first.", "warn")
            return None
        raw = ask(prompt)
        if raw is None:
            return QUIT
        if not raw.strip().lstrip("-").isdigit():
            self.status = (f"Enter a number from the list, not {raw!r}.", "error")
            return None
        number = int(raw)
        if not 1 <= number <= len(self.shown):
            self.status = (f"Pick 1-{len(self.shown)}.", "error")
            return None
        return self.shown[number - 1]

    def confirm(self, prompt: str) -> bool:
        raw = ask(prompt + " [y/N] ")
        return raw is not None and raw.strip().lower() in ("y", "yes")

    def ask_field(self, prompt: str, decode, default):
        """Re-ask until the answer makes sense, so a typo never loses the whole entry."""
        while True:
            raw = ask(prompt)
            if raw is None:
                return QUIT
            if not raw.strip():
                return default
            try:
                return decode(raw)
            except ValueError as error:
                print(style.message(str(error), "error"))

    # ---------- commands ----------
    def add(self) -> object:
        description = ask("  Task: ")
        if description is None:
            return QUIT
        description = description.strip()
        if not description:
            self.status = ("A task needs a description.", "error")
            return None
        priority = self.ask_field(
            "  Priority low/medium/high [Enter = medium]: ", Priority.decode, Priority.MEDIUM
        )
        if priority is QUIT:
            return QUIT
        due = self.ask_field(
            "  Due date 2026-10-31, +5, tomorrow [Enter = none]: ",
            lambda text: parse_due(text, self.today),
            None,
        )
        if due is QUIT:
            return QUIT
        notes = (ask("  Notes [Enter = none]: ") or "").strip()
        task = self.todo.add_task(description, priority, due, notes)
        self.status = (f"Added: {task.description}", "ok")
        return None

    def toggle(self) -> None:
        task = self.pick_number("  Number to toggle: ")
        if task is QUIT:
            return QUIT
        if task is None:
            return
        now_done = task.toggle()
        self.todo.save_tasks()
        self.status = (
            f"{'Completed' if now_done else 'Reopened'}: {task.description}",
            "ok" if now_done else "info",
        )

    def edit(self) -> object:
        task = self.pick_number("  Number to edit: ")
        if task is QUIT:
            return QUIT
        if task is None:
            return None
        print(
            style.paint(
                f"  current: {task.description} | {task.priority.label}"
                f" | due {task.due or 'none'} | notes {task.notes or 'none'}",
                style.DIM,
            )
        )
        description = self.ask_field(
            "  new description (Enter keeps): ", str.strip, task.description
        )
        priority = self.ask_field(
            "  priority low/medium/high (Enter keeps): ", Priority.decode, task.priority
        )
        # '-' clears the date, Enter leaves it alone.
        due = self.ask_field(
            "  due date, - to clear (Enter keeps): ",
            lambda text: parse_due(text, self.today),
            task.due,
        )
        notes = self.ask_field("  notes (Enter keeps): ", str.strip, task.notes)
        if QUIT in (description, priority, due, notes):
            return QUIT

        task.description = description
        task.priority = priority
        task.due = due
        task.notes = notes
        self.todo.save_tasks()
        self.status = (f"Updated: {task.description}", "ok")
        return None

    def remove(self) -> None:
        task = self.pick_number("  Number to remove: ")
        if task is QUIT:
            return QUIT
        if task is None:
            return
        if not self.confirm(f"  Remove '{task.description}'?"):
            self.status = ("Nothing removed.", "info")
            return
        self.todo.remove_task(task)
        self.status = (f"Removed: {task.description}", "warn")

    def filter_view(self) -> None:
        print(
            "\n".join(
                f"  {index}. {name:<9} {style.paint(VIEW_LABELS[name], style.GREY)}"
                for index, name in enumerate(VIEWS, start=1)
            )
        )
        raw = ask("  Show which? ")
        if raw is None:
            return QUIT
        if raw.strip().isdigit() and 1 <= int(raw) <= len(VIEWS):
            self.view = VIEWS[int(raw) - 1]
            self.status = (f"Showing {VIEW_LABELS[self.view]}.", "info")
        else:
            self.status = ("Choose one of the listed numbers.", "error")

    def search(self) -> None:
        raw = ask("  Search text (Enter clears): ")
        if raw is None:
            return QUIT
        self.query = raw.strip()
        self.status = (
            (f"Filtering for '{self.query}'." if self.query else "Search cleared."),
            "info",
        )

    def clear_done(self) -> None:
        done = [task for task in self.todo.tasks if task.completed]
        if not done:
            self.status = ("No completed tasks to clear.", "info")
            return
        if not self.confirm(f"  Delete {len(done)} completed task(s)?"):
            self.status = ("Nothing cleared.", "info")
            return
        removed = self.todo.clear_completed()
        self.status = (f"Cleared {removed} completed task(s).", "warn")

    def stats(self) -> None:
        counts = self.todo.counts(self.today)
        lines = [
            f"  total       {counts['total']}",
            f"  open        {counts['open']}",
            f"  done        {counts['done']}",
            f"  overdue     {style.paint(str(counts['overdue']), style.RED if counts['overdue'] else style.GREY)}",
            f"  high open   {counts['high']}",
            f"  with notes  {counts['with_notes']}",
            "  " + style.progress_bar(counts["done"], counts["total"]),
        ]
        print(style.panel(" STATS ", lines))
        self.status = ("Press Enter to continue.", "info")
        ask("")

    # ---------- loop ----------
    def handle(self, choice: str) -> object:
        actions = {
            "1": lambda: None,
            "r": lambda: None,
            "2": self.add,
            "3": self.toggle,
            "4": self.edit,
            "5": self.remove,
            "6": self.filter_view,
            "7": self.search,
            "8": self.clear_done,
            "9": self.stats,
        }
        if choice in ("0", "q", "quit"):
            return QUIT
        action = actions.get(choice)
        if action is None:
            self.status = (f"Unknown option: {choice!r}", "error")
            return None
        return action()

    def run(self) -> None:
        while True:
            self.draw()
            choice = ask("\n  Choice: ")
            if choice is None:
                break
            result = self.handle(choice.strip().lower())
            if result is QUIT:
                break
        print(style.message("Saved. Bye!", "ok"))


def main() -> None:
    filename = sys.argv[1] if len(sys.argv) > 1 else "tasks.json"
    try:
        App(filename).run()
    except OSError as error:
        raise SystemExit(f"Cannot write tasks: {error}")


if __name__ == "__main__":
    main()
