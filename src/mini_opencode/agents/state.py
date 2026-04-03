from typing import Any

from langgraph.graph import MessagesState

from mini_opencode.tools.todo import TodoItem

from .types import (
    CoordinationState,
    ParentTask,
    SubTask,
    WorkerResult,
)


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


class MultiAgentState(MessagesState):
    """State for multi-agent collaboration.

    This state extends the basic MessagesState to support multi-agent
    coordination with Manager-Worker pattern.

    Attributes:
        todos: List of todo items for task tracking.
        memory_context: Context from long-term memory to enhance responses.
        user_id: Unique identifier for the user.
        parent_task: The parent task from user request.
        subtasks: List of sub-tasks for workers.
        worker_results: Results from worker executions.
        coordination: Coordination state for workflow management.
        active_workers: Set of currently active worker IDs.
        shared_context: Shared context data accessible by all agents.
    """

    # Inherited from CodingAgentState
    todos: list[TodoItem]
    memory_context: str
    user_id: str

    # Multi-agent specific fields
    parent_task: ParentTask | None
    subtasks: list[SubTask]
    worker_results: dict[str, WorkerResult]
    coordination: CoordinationState
    active_workers: set[str]
    shared_context: dict[str, Any]

    @classmethod
    def create_initial(
        cls,
        user_id: str = "default",
        memory_context: str = "",
    ) -> dict[str, Any]:
        """Create initial state for a new multi-agent session.

        Args:
            user_id: The user identifier.
            memory_context: Initial memory context.

        Returns:
            Initial state dictionary.
        """
        return {
            "messages": [],
            "todos": [],
            "memory_context": memory_context,
            "user_id": user_id,
            "parent_task": None,
            "subtasks": [],
            "worker_results": {},
            "coordination": CoordinationState(),
            "active_workers": set(),
            "shared_context": {},
        }
