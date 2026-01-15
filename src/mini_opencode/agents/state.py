from langgraph.graph import MessagesState
from pydantic import Field

from mini_opencode.tools.todo import TodoItem


class CodingAgentState(MessagesState):
    todos: list[TodoItem] = Field(default_factory=list)
