from todo import TodoList

def main():
    todo = TodoList()
    while True:
        print("\n1. List Tasks\n2. Add Task\n3. Remove Task\n4. Exit")
        choice = input("Choose an option: ")
        if choice == "1":
            todo.list_tasks()
        elif choice == "2":
            desc = input("Task description: ")
            todo.add_task(desc)
        elif choice == "3":
            index = int(input("Task number to remove: ")) - 1
            todo.remove_task(index)
        elif choice == "4":
            break
        else:
            print("Invalid choice!")

if __name__ == "__main__":
    main()
