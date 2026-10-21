# src/todo.py
"""Task model and JSON persistence. Presentation lives in style.py / main.py."""

from __future__ import annotations

import enum
import json
import os
from datetime import date, timedelta


class Priority(enum.Enum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2

    @property
    def label(self) -> str:
        return self.name.title()

    @classmethod
    def decode(cls, text: str) -> "Priority":
        """Used by the prompts, so a typo is reported instead of silently becoming medium."""
        priority = cls.try_parse(text)
        if priority is None:
            raise ValueError(f"unknown priority {text!r} - use low, medium or high")
        return priority

    @classmethod
    def try_parse(cls, text: str) -> "Priority | None":
        aliases = {
            "": cls.MEDIUM,
            "1": cls.LOW,
            "2": cls.MEDIUM,
            "3": cls.HIGH,
            "l": cls.LOW,
            "low": cls.LOW,
            "m": cls.MEDIUM,
            "medium": cls.MEDIUM,
            "normal": cls.MEDIUM,
            "h": cls.HIGH,
            "high": cls.HIGH,
        }
        return aliases.get(text.strip().lower())


def parse_due(text: str, today: date | None = None) -> date | None:
    """Accept ISO dates, '+7' days, and the words today/tomorrow."""
    raw = text.strip().lower()
    if raw in ("", "-", "none", "no"):
        return None
    today = today or date.today()
    if raw == "today":
        return today
    if raw == "tomorrow":
        return today + timedelta(days=1)
    if raw.startswith("+") and raw[1:].isdigit():
        return today + timedelta(days=int(raw[1:]))
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return date.strptime(raw, fmt)
        except ValueError:
            continue
    raise ValueError(f"not a date: {text!r} (use 2026-10-31, +5 or tomorrow)")


class Task:
    def __init__(
        self,
        description: str,
        priority: Priority = Priority.MEDIUM,
        due: date | None = None,
        notes: str = "",
        completed: bool = False,
    ):
        self.description = description
        self.priority = priority
        self.due = due
        self.notes = notes
        self.completed = completed

    def mark_done(self) -> None:
        self.completed = True

    def mark_undone(self) -> None:
        self.completed = False

    def toggle(self) -> bool:
        self.completed = not self.completed
        return self.completed

    def is_overdue(self, today: date | None = None) -> bool:
        return bool(self.due and not self.completed and self.due < (today or date.today()))

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "completed": self.completed,
            "priority": self.priority.name,
            "due": self.due.isoformat() if self.due else None,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        due = None
        raw_due = data.get("due")
        if raw_due:
            try:
                due = date.fromisoformat(raw_due)
            except (TypeError, ValueError):
                due = None
        try:
            priority = Priority[data.get("priority", "MEDIUM")]
        except KeyError:
            priority = Priority.MEDIUM
        return cls(
            description=str(data.get("description", "")).strip() or "untitled",
            priority=priority,
            due=due,
            notes=str(data.get("notes", "")),
            completed=bool(data.get("completed", False)),
        )

    def __repr__(self) -> str:
        status = "done" if self.completed else "open"
        return f"<{status} {self.priority.name[0]} {self.description}>"


VIEWS = ("all", "open", "done", "overdue", "high")


class TodoList:
    def __init__(self, filename: str = "tasks.json"):
        self.tasks: list[Task] = []
        self.filename = filename
        self.load_tasks()

    def add_task(
        self,
        description: str,
        priority: Priority = Priority.MEDIUM,
        due: date | None = None,
        notes: str = "",
    ) -> Task:
        task = Task(description.strip(), priority, due, notes.strip())
        self.tasks.append(task)
        self.save_tasks()
        return task

    def get(self, number: int) -> Task | None:
        """Fetch a task by its 1-based display number."""
        if 1 <= number <= len(self.tasks):
            return self.tasks[number - 1]
        return None

    def remove_task(self, task: Task) -> None:
        self.tasks.remove(task)
        self.save_tasks()

    def clear_completed(self) -> int:
        removed = sum(1 for task in self.tasks if task.completed)
        self.tasks = [task for task in self.tasks if not task.completed]
        if removed:
            self.save_tasks()
        return removed

    def visible(self, view: str = "all", query: str = "", today: date | None = None) -> list[Task]:
        today = today or date.today()
        if view == "open":
            tasks = [t for t in self.tasks if not t.completed]
        elif view == "done":
            tasks = [t for t in self.tasks if t.completed]
        elif view == "overdue":
            tasks = [t for t in self.tasks if t.is_overdue(today)]
        elif view == "high":
            tasks = [t for t in self.tasks if t.priority is Priority.HIGH and not t.completed]
        else:
            tasks = list(self.tasks)
        needle = query.strip().lower()
        if needle:
            tasks = [
                t
                for t in tasks
                if needle in t.description.lower() or needle in t.notes.lower()
            ]
        return tasks

    def counts(self, today: date | None = None) -> dict:
        today = today or date.today()
        total = len(self.tasks)
        done = sum(1 for t in self.tasks if t.completed)
        return {
            "total": total,
            "done": done,
            "open": total - done,
            "overdue": sum(1 for t in self.tasks if t.is_overdue(today)),
            "high": sum(1 for t in self.tasks if t.priority is Priority.HIGH and not t.completed),
            "with_notes": sum(1 for t in self.tasks if t.notes),
        }

    def save_tasks(self) -> None:
        data = [task.to_dict() for task in self.tasks]
        directory = os.path.dirname(os.path.abspath(self.filename))
        os.makedirs(directory, exist_ok=True)
        # Write-then-replace, so a crash mid-write cannot destroy the real file.
        temp = f"{self.filename}.tmp"
        with open(temp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=4, ensure_ascii=False)
        os.replace(temp, self.filename)

    def load_tasks(self) -> None:
        try:
            with open(self.filename, encoding="utf-8") as handle:
                raw = handle.read()
        except FileNotFoundError:
            self.tasks = []
            return
        try:
            data = json.loads(raw or "[]")
        except json.JSONDecodeError as error:
            raise SystemExit(f"{self.filename} is not valid JSON: {error}")
        if not isinstance(data, list):
            raise SystemExit(f"{self.filename} must contain a JSON list of tasks")
        self.tasks = [Task.from_dict(item) for item in data if isinstance(item, dict)]
