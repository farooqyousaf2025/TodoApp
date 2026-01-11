import unittest
from src.todo import Task, TodoList

class TestTodoList(unittest.TestCase):
    def test_add_task(self):
        todo = TodoList(filename="test_tasks.json")
        todo.tasks = []
        todo.add_task("Test Task")
        self.assertEqual(len(todo.tasks), 1)
        self.assertEqual(todo.tasks[0].description, "Test Task")

    def test_mark_done(self):
        task = Task("Sample Task")
        task.mark_done()
        self.assertTrue(task.completed)

if __name__ == "__main__":
    unittest.main()
