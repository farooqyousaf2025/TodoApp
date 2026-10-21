import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from src.todo import Priority, Task, TodoList, parse_due

TODAY = date(2026, 10, 21)


class TestTask(unittest.TestCase):
    def test_mark_done(self):
        task = Task("Sample Task")
        task.mark_done()
        self.assertTrue(task.completed)

    def test_toggle(self):
        task = Task("Sample Task")
        self.assertTrue(task.toggle())
        self.assertFalse(task.toggle())

    def test_overdue_only_when_open(self):
        task = Task("Late", due=TODAY - timedelta(days=1))
        self.assertTrue(task.is_overdue(TODAY))
        task.mark_done()
        self.assertFalse(task.is_overdue(TODAY))

    def test_defaults(self):
        task = Task("Plain")
        self.assertEqual(task.priority, Priority.MEDIUM)
        self.assertIsNone(task.due)
        self.assertEqual(task.notes, "")


class TestTodoList(unittest.TestCase):
    def setUp(self):
        handle, self.filename = tempfile.mkstemp(suffix=".json")
        os.close(handle)
        os.remove(self.filename)
        self.todo = TodoList(filename=self.filename)

    def tearDown(self):
        if os.path.exists(self.filename):
            os.remove(self.filename)

    def test_add_task(self):
        self.todo.tasks = []
        self.todo.add_task("Test Task")
        self.assertEqual(len(self.todo.tasks), 1)
        self.assertEqual(self.todo.tasks[0].description, "Test Task")

    def test_get_by_display_number(self):
        self.todo.add_task("First")
        self.todo.add_task("Second")
        self.assertEqual(self.todo.get(1).description, "First")
        self.assertIsNone(self.todo.get(0))
        self.assertIsNone(self.todo.get(3))

    def test_remove_task(self):
        task = self.todo.add_task("Doomed")
        self.todo.remove_task(task)
        self.assertEqual(self.todo.tasks, [])

    def test_round_trip_keeps_priority_due_and_notes(self):
        self.todo.add_task(
            "Write report", Priority.HIGH, TODAY + timedelta(days=2), "two pages"
        )
        reloaded = TodoList(filename=self.filename)
        task = reloaded.tasks[0]
        self.assertEqual(task.priority, Priority.HIGH)
        self.assertEqual(task.due, TODAY + timedelta(days=2))
        self.assertEqual(task.notes, "two pages")

    def test_empty_file_counts_as_no_tasks(self):
        with open(self.filename, "w", encoding="utf-8"):
            pass
        self.assertEqual(TodoList(filename=self.filename).tasks, [])

    def test_loads_old_format_without_new_fields(self):
        legacy = [{"description": "Old Task", "completed": True}]
        with open(self.filename, "w", encoding="utf-8") as handle:
            json.dump(legacy, handle)
        todo = TodoList(filename=self.filename)
        task = todo.tasks[0]
        self.assertEqual(task.priority, Priority.MEDIUM)
        self.assertTrue(task.completed)
        self.assertIsNone(task.due)

    def test_bad_due_date_in_file_is_ignored(self):
        with open(self.filename, "w", encoding="utf-8") as handle:
            json.dump([{"description": "X", "completed": False, "due": "not-a-date"}], handle)
        self.assertIsNone(TodoList(filename=self.filename).tasks[0].due)

    def test_saving_leaves_no_temp_file(self):
        self.todo.add_task("Persisted")
        self.assertFalse(os.path.exists(self.filename + ".tmp"))

    def test_views_and_search(self):
        open_task = self.todo.add_task("Buy milk", Priority.HIGH)
        done_task = self.todo.add_task("Pay rent")
        done_task.mark_done()
        self.todo.save_tasks()
        old = self.todo.add_task("Tax return", due=TODAY - timedelta(days=1))

        self.assertEqual(len(self.todo.visible("all")), 3)
        self.assertEqual(self.todo.visible("done"), [done_task])
        self.assertEqual(self.todo.visible("overdue"), [old])
        self.assertEqual(self.todo.visible("high"), [open_task])
        self.assertEqual(self.todo.visible("all", "milk"), [open_task])
        self.assertEqual(self.todo.visible("open", "tax"), [old])

    def test_clear_completed(self):
        task = self.todo.add_task("Finished")
        task.mark_done()
        self.todo.add_task("Keep me")
        self.assertEqual(self.todo.clear_completed(), 1)
        self.assertEqual([t.description for t in self.todo.tasks], ["Keep me"])
        self.assertEqual(TodoList(filename=self.filename).tasks[0].description, "Keep me")

    def test_counts(self):
        self.todo.add_task("Late", due=TODAY - timedelta(days=3))
        self.todo.add_task("High", Priority.HIGH)
        counts = self.todo.counts(TODAY)
        self.assertEqual(counts["total"], 2)
        self.assertEqual(counts["overdue"], 1)
        self.assertEqual(counts["high"], 1)
        self.assertEqual(counts["done"], 0)


class TestParseDue(unittest.TestCase):
    def test_iso_and_relative(self):
        self.assertEqual(parse_due("2026-10-31", TODAY), date(2026, 10, 31))
        self.assertEqual(parse_due("31/10/2026", TODAY), date(2026, 10, 31))
        self.assertEqual(parse_due("+7", TODAY), date(2026, 10, 28))
        self.assertEqual(parse_due("tomorrow", TODAY), date(2026, 10, 22))
        self.assertEqual(parse_due("today", TODAY), TODAY)

    def test_empty_clears(self):
        for text in ("", "-", "none", "   "):
            self.assertIsNone(parse_due(text, TODAY))

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            parse_due("next week", TODAY)

    def test_priority_aliases(self):
        self.assertIs(Priority.try_parse("h"), Priority.HIGH)
        self.assertIs(Priority.try_parse("3"), Priority.HIGH)
        self.assertIs(Priority.try_parse("LOW"), Priority.LOW)
        self.assertIs(Priority.try_parse(""), Priority.MEDIUM)
        self.assertIsNone(Priority.try_parse("banana"))
        self.assertIs(Priority.decode("m"), Priority.MEDIUM)

    def test_decode_rejects_unknown_priority(self):
        with self.assertRaises(ValueError):
            Priority.decode("banana")


class TestPrompts(unittest.TestCase):
    """A typo while typing a task must not throw the whole entry away."""

    def setUp(self):
        handle, self.filename = tempfile.mkstemp(suffix=".json")
        os.close(handle)
        os.remove(self.filename)
        from src.main import App

        self.app = App(self.filename)

    def tearDown(self):
        for path in (self.filename, self.filename + ".tmp"):
            if os.path.exists(path):
                os.remove(path)

    def feed(self, answers):
        return list(answers)

    def test_ask_field_repeats_until_valid(self):
        from src.todo import Priority

        with patch("builtins.input", side_effect=self.feed(["banana", "h"])) as prompts:
            self.assertIs(
                self.app.ask_field("p: ", Priority.decode, Priority.MEDIUM), Priority.HIGH
            )
            self.assertEqual(prompts.call_count, 2)

    def test_ask_field_blank_returns_default(self):
        with patch("builtins.input", side_effect=self.feed([""])):
            self.assertIs(
                self.app.ask_field("p: ", Priority.decode, Priority.LOW), Priority.LOW
            )

    def test_add_keeps_description_when_due_is_retyped(self):
        answers = self.feed(["Write the report", "x", "high", "next week", "2026-11-05", "note"])
        with patch("builtins.input", side_effect=answers):
            self.app.add()
        task = self.app.todo.tasks[0]
        self.assertEqual(task.description, "Write the report")
        self.assertEqual(task.priority, Priority.HIGH)
        self.assertEqual(task.due, date(2026, 11, 5))
        self.assertEqual(task.notes, "note")

    def test_add_rejects_missing_description(self):
        with patch("builtins.input", side_effect=self.feed(["   "])):
            self.app.add()
        self.assertEqual(self.app.todo.tasks, [])
        self.assertEqual(self.app.status[1], "error")

    def test_edit_keeps_untouched_fields(self):
        task = self.app.todo.add_task("Original", Priority.LOW, date(2026, 12, 1), "keep me")
        self.app.shown = [task]
        answers = self.feed(["1", "", "", "", "changed note"])
        with patch("builtins.input", side_effect=answers):
            self.app.edit()
        self.assertEqual(task.description, "Original")
        self.assertEqual(task.priority, Priority.LOW)
        self.assertEqual(task.due, date(2026, 12, 1))
        self.assertEqual(task.notes, "changed note")

    def test_pick_number_rejects_bad_input(self):
        task = self.app.todo.add_task("Only task")
        self.app.shown = [task]
        with patch("builtins.input", side_effect=self.feed(["seven"])):
            self.assertIsNone(self.app.pick_number("Number: "))
        with patch("builtins.input", side_effect=self.feed(["9"])):
            self.assertIsNone(self.app.pick_number("Number: "))
        with patch("builtins.input", side_effect=self.feed(["1"])):
            self.assertIs(self.app.pick_number("Number: "), task)

    def test_pick_number_without_tasks(self):
        self.app.shown = []
        self.assertIsNone(self.app.pick_number("Number: "))
        self.assertEqual(self.app.status[1], "warn")

    def test_ctrl_c_exits_the_loop(self):
        from src.main import QUIT

        with patch("builtins.input", side_effect=KeyboardInterrupt):
            self.assertIs(self.app.add(), QUIT)


if __name__ == "__main__":
    unittest.main()
