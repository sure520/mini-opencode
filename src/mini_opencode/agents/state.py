from langgraph.graph import MessagesState

from mini_opencode.tools.todo import TodoItem


class CodingAgentState(MessagesState):
    todos: list[TodoItem]
