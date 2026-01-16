from langchain.tools import ToolRuntime

from mini_opencode.tools.todo import TodoStatus


def generate_reminders(runtime: ToolRuntime) -> str:
    """
    Generate a formatted reminder string based on unfinished TODO items.

    Args:
        runtime: The ToolRuntime object containing the current agent state.

    Returns:
        A string containing formatted reminders, or an empty string if no reminders are needed.
    """
    todos = runtime.state.get("todos") or []
    unfinished_todos = [
        todo
        for todo in todos
        if todo.status not in (TodoStatus.completed, TodoStatus.cancelled)
    ]

    if not unfinished_todos:
        return "All tasks completed. You can now reply to the user."

    status_summary = ", ".join([f"#{t.id} {t.title}" for t in unfinished_todos[:3]])
    if len(unfinished_todos) > 3:
        status_summary += f" and {len(unfinished_todos) - 3} more"

    return (
        f"--- TASK STATUS ---\n"
        f"Pending: {status_summary}\n"
        f"Action: Complete these before finishing. Use 'todo_write' to track progress."
    )
