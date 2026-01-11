# src/todo.py

import json

class Task:
    def __init__(self, description):
        self.description = description
        self.completed = False

    def mark_done(self):
        self.completed = True

    def __repr__(self):
        status = "✔" if self.completed else "✘"
        return f"[{status}] {self.description}"


class TodoList:
    def __init__(self, filename="tasks.json"):
        self.tasks = []
        self.filename = filename
        self.load_tasks()

    def add_task(self, description):
        task = Task(description)
        self.tasks.append(task)
        self.save_tasks()

    def remove_task(self, index):
        if 0 <= index < len(self.tasks):
            self.tasks.pop(index)
            self.save_tasks()

    def list_tasks(self):
        for i, task in enumerate(self.tasks):
            print(f"{i+1}. {task}")

    def save_tasks(self):
        data = [{"description": t.description, "completed": t.completed} for t in self.tasks]
        with open(self.filename, "w") as f:
            json.dump(data, f, indent=4)

    def load_tasks(self):
        try:
            with open(self.filename, "r") as f:
                data = json.load(f)
                self.tasks = [Task(d["description"]) for d in data]
                for task, d in zip(self.tasks, data):
                    task.completed = d["completed"]
        except FileNotFoundError:
            self.tasks = []

