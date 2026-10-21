import os
import tempfile
import unittest
from contextlib import asynccontextmanager
from datetime import date, timedelta

from textual.widgets import DataTable, Input, Select

from src.todo import Priority, TodoList
from src.tui_app import ConfirmScreen, TaskFormScreen, TodoTUI

TODAY = date(2026, 10, 21)
SIZE = (100, 40)


async def settle(pilot, rounds: int = 5) -> None:
    """Let Textual process messages before asserting."""
    for _ in range(rounds):
        await pilot.pause()


class TestTUI(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        handle, self.filename = tempfile.mkstemp(suffix=".json")
        os.close(handle)
        todo = TodoList(self.filename)
        self.open_task = todo.add_task(
            "Renew insurance", Priority.HIGH, TODAY - timedelta(days=2), "call broker"
        )
        todo.add_task("Pay electricity", Priority.MEDIUM, TODAY + timedelta(days=5))
        done = todo.add_task("Book dentist")
        done.mark_done()
        todo.save_tasks()

    async def asyncTearDown(self):
        for path in (self.filename, self.filename + ".tmp"):
            if os.path.exists(path):
                os.remove(path)

    @asynccontextmanager
    async def running(self):
        app = TodoTUI(self.filename)
        async with app.run_test(size=SIZE) as pilot:
            await settle(pilot)
            yield app, pilot

    async def test_table_lists_every_task(self):
        async with self.running() as (app, pilot):
            self.assertEqual(app.query_one(DataTable).row_count, 3)
            self.assertEqual(len(app.shown), 3)

    async def test_add_flow_creates_and_persists(self):
        async with self.running() as (app, pilot):
            await pilot.press("a")
            await settle(pilot)
            self.assertIsInstance(app.screen, TaskFormScreen)

            screen = app.screen
            screen.query_one("#field_description", Input).value = "Buy bread"
            screen.query_one("#field_due", Input).value = "+3"
            await pilot.press("enter")
            await settle(pilot)

            self.assertEqual(len(app.todo.tasks), 4)
            self.assertEqual(app.todo.tasks[-1].description, "Buy bread")
            self.assertEqual(app.todo.tasks[-1].due, TODAY + timedelta(days=3))
            self.assertEqual(len(TodoList(self.filename).tasks), 4)
            self.assertNotIsInstance(app.screen, TaskFormScreen)

    async def test_blank_description_is_rejected(self):
        async with self.running() as (app, pilot):
            await pilot.press("a")
            await settle(pilot)
            await pilot.press("enter")
            await settle(pilot)
            self.assertIsInstance(app.screen, TaskFormScreen)
            self.assertEqual(len(app.todo.tasks), 3)

    async def test_invalid_due_date_keeps_the_dialog_open(self):
        async with self.running() as (app, pilot):
            await pilot.press("a")
            await settle(pilot)
            screen = app.screen
            screen.query_one("#field_description", Input).value = "Keep this text"
            screen.query_one("#field_due", Input).value = "next week"
            await pilot.press("enter")
            await settle(pilot)
            self.assertIsInstance(app.screen, TaskFormScreen)
            self.assertIn("not a date", screen.query_one("#form_error").render().plain)
            self.assertEqual(len(app.todo.tasks), 3)

    async def test_escape_cancels_the_dialog(self):
        async with self.running() as (app, pilot):
            await pilot.press("a")
            await settle(pilot)
            await pilot.press("escape")
            await settle(pilot)
            self.assertNotIsInstance(app.screen, TaskFormScreen)
            self.assertEqual(len(app.todo.tasks), 3)

    async def test_space_toggles_selected_row(self):
        async with self.running() as (app, pilot):
            app.query_one(DataTable).focus()
            await settle(pilot)
            await pilot.press("space")
            await settle(pilot)
            self.assertTrue(app.todo.tasks[0].completed)
            self.assertTrue(TodoList(self.filename).tasks[0].completed)

    async def test_edit_updates_fields(self):
        async with self.running() as (app, pilot):
            app.query_one(DataTable).focus()
            await settle(pilot)
            await pilot.press("e")
            await settle(pilot)
            screen = app.screen
            self.assertEqual(
                screen.query_one("#field_description", Input).value, "Renew insurance"
            )
            screen.query_one("#field_notes", Input).value = "edited notes"
            await pilot.press("enter")
            await settle(pilot)
            self.assertEqual(app.todo.tasks[0].notes, "edited notes")
            self.assertEqual(app.todo.tasks[0].priority, Priority.HIGH)

    async def test_delete_needs_confirmation(self):
        async with self.running() as (app, pilot):
            app.query_one(DataTable).focus()
            await settle(pilot)
            await pilot.press("d")
            await settle(pilot)
            self.assertIsInstance(app.screen, ConfirmScreen)
            await pilot.click("#btn_yes")
            await settle(pilot)
            self.assertEqual(len(app.todo.tasks), 2)
            self.assertNotIn(self.open_task, app.todo.tasks)

    async def test_mouse_row_click_toggles(self):
        async with self.running() as (app, pilot):
            # Inside the table: row 0 is the border, row 1 the header, row 2 the first task.
            await pilot.click(DataTable, offset=(6, 2))
            await settle(pilot)
            self.assertTrue(app.todo.tasks[0].completed)

    async def test_search_filters_rows(self):
        async with self.running() as (app, pilot):
            search = app.query_one("#search", Input)
            search.value = "dentist"
            await settle(pilot)
            self.assertEqual([t.description for t in app.shown], ["Book dentist"])
            search.value = ""
            await settle(pilot)
            self.assertEqual(len(app.shown), 3)

    async def test_view_select_filters_rows(self):
        async with self.running() as (app, pilot):
            app.query_one("#view_select", Select).value = "overdue"
            await settle(pilot)
            self.assertEqual([t.description for t in app.shown], ["Renew insurance"])
            self.assertEqual(app.view, "overdue")

    async def test_next_view_binding_cycles(self):
        async with self.running() as (app, pilot):
            app.query_one(DataTable).focus()
            await settle(pilot)
            await pilot.press("f")
            await settle(pilot)
            self.assertEqual(app.view, "open")
            self.assertEqual(str(app.query_one("#view_select", Select).value), "open")


if __name__ == "__main__":
    unittest.main()
