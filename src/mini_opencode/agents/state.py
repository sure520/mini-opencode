from langgraph.graph import MessagesState

from mini_opencode.tools.todo import TodoItem


class CodingAgentState(MessagesState):
    """State for the coding agent with memory support.

    Attributes:
        todos: List of todo items for task tracking.
        memory_context: Context from long-term memory to enhance responses.
        user_id: Unique identifier for the user.
    """

    todos: list[TodoItem]
    memory_context: str
    user_id: str
