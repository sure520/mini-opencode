"""Type definitions for multi-agent architecture."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TaskType(Enum):
    """Type of task to be executed by workers."""

    CODER = "coder"
    DEBUGGER = "debugger"
    TESTER = "tester"
    REVIEWER = "reviewer"


class TaskStatus(Enum):
    """Status of a task in the workflow."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CoordinationPhase(Enum):
    """Phase of the multi-agent coordination."""

    PLANNING = "planning"
    EXECUTING = "executing"
    AGGREGATING = "aggregating"
    COMPLETED = "completed"


@dataclass
class SubTask:
    """Represents a sub-task assigned to a worker.

    Attributes:
        task_id: Unique identifier for the task.
        task_type: Type of task (coder, debugger, tester).
        description: Detailed description of what needs to be done.
        status: Current status of the task.
        assigned_worker: ID of the worker assigned to this task.
        dependencies: List of task IDs this task depends on.
        result: Execution result after completion.
        error: Error message if task failed.
        created_at: Timestamp when the task was created.
        completed_at: Timestamp when the task was completed.
        context: Additional context data for the task.
    """

    task_id: str
    task_type: TaskType
    description: str
    status: TaskStatus = TaskStatus.PENDING
    assigned_worker: str | None = None
    dependencies: list[str] = field(default_factory=list)
    result: Any = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    context: dict[str, Any] = field(default_factory=dict)

    def is_ready(self, completed_tasks: set[str]) -> bool:
        """Check if all dependencies are completed.

        Args:
            completed_tasks: Set of completed task IDs.

        Returns:
            True if all dependencies are satisfied.
        """
        return all(dep in completed_tasks for dep in self.dependencies)

    def mark_running(self, worker_id: str) -> None:
        """Mark the task as running.

        Args:
            worker_id: ID of the worker executing this task.
        """
        self.status = TaskStatus.RUNNING
        self.assigned_worker = worker_id

    def mark_completed(self, result: Any) -> None:
        """Mark the task as completed.

        Args:
            result: The execution result.
        """
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.completed_at = datetime.now()

    def mark_failed(self, error: str) -> None:
        """Mark the task as failed.

        Args:
            error: The error message.
        """
        self.status = TaskStatus.FAILED
        self.error = error
        self.completed_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "description": self.description,
            "status": self.status.value,
            "assigned_worker": self.assigned_worker,
            "dependencies": self.dependencies,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubTask":
        """Create a SubTask from dictionary."""
        return cls(
            task_id=data["task_id"],
            task_type=TaskType(data["task_type"]),
            description=data["description"],
            status=TaskStatus(data["status"]),
            assigned_worker=data.get("assigned_worker"),
            dependencies=data.get("dependencies", []),
            result=data.get("result"),
            error=data.get("error"),
            created_at=datetime.fromisoformat(data["created_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
            context=data.get("context", {}),
        )


@dataclass
class ParentTask:
    """Represents the parent task from user request.

    Attributes:
        task_id: Unique identifier for the parent task.
        original_request: The original user request.
        subtasks: List of sub-task IDs.
        created_at: Timestamp when the task was created.
        completed_at: Timestamp when the task was completed.
    """

    task_id: str
    original_request: str
    subtasks: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "original_request": self.original_request,
            "subtasks": self.subtasks,
            "created_at": self.created_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }


@dataclass
class CoordinationState:
    """State for coordinating multi-agent workflow.

    Attributes:
        phase: Current phase of coordination.
        parallel_groups: Groups of tasks that can be executed in parallel.
        completed_count: Number of completed tasks.
        failed_count: Number of failed tasks.
        iteration_count: Current iteration count (for retry loops).
        max_iterations: Maximum allowed iterations.
    """

    phase: CoordinationPhase = CoordinationPhase.PLANNING
    parallel_groups: list[list[str]] = field(default_factory=list)
    completed_count: int = 0
    failed_count: int = 0
    iteration_count: int = 0
    max_iterations: int = 3

    def can_iterate(self) -> bool:
        """Check if more iterations are allowed."""
        return self.iteration_count < self.max_iterations

    def increment_iteration(self) -> None:
        """Increment the iteration count."""
        self.iteration_count += 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "phase": self.phase.value,
            "parallel_groups": self.parallel_groups,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "iteration_count": self.iteration_count,
            "max_iterations": self.max_iterations,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CoordinationState":
        """Create a CoordinationState from dictionary."""
        return cls(
            phase=CoordinationPhase(data["phase"]),
            parallel_groups=data.get("parallel_groups", []),
            completed_count=data.get("completed_count", 0),
            failed_count=data.get("failed_count", 0),
            iteration_count=data.get("iteration_count", 0),
            max_iterations=data.get("max_iterations", 3),
        )


@dataclass
class WorkerResult:
    """Result from a worker execution.

    Attributes:
        worker_id: ID of the worker.
        task_id: ID of the task executed.
        success: Whether execution was successful.
        output: Output content from the worker.
        error: Error message if failed.
        tool_calls: List of tool calls made during execution.
        execution_time_ms: Execution time in milliseconds.
    """

    worker_id: str
    task_id: str
    success: bool
    output: str = ""
    error: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    execution_time_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "worker_id": self.worker_id,
            "task_id": self.task_id,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "tool_calls": self.tool_calls,
            "execution_time_ms": self.execution_time_ms,
        }


@dataclass
class TaskPlan:
    """Plan generated by the manager for task execution.

    Attributes:
        plan_id: Unique identifier for the plan.
        parent_task: The parent task being planned.
        subtasks: List of subtasks to execute.
        execution_order: Ordered list of task groups for execution.
        estimated_duration_ms: Estimated total execution time.
    """

    plan_id: str
    parent_task: ParentTask
    subtasks: list[SubTask]
    execution_order: list[list[str]] = field(default_factory=list)
    estimated_duration_ms: int = 0

    def get_ready_tasks(self, completed_tasks: set[str]) -> list[SubTask]:
        """Get tasks that are ready to execute.

        Args:
            completed_tasks: Set of completed task IDs.

        Returns:
            List of tasks ready for execution.
        """
        return [
            task
            for task in self.subtasks
            if task.status == TaskStatus.PENDING and task.is_ready(completed_tasks)
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "plan_id": self.plan_id,
            "parent_task": self.parent_task.to_dict(),
            "subtasks": [t.to_dict() for t in self.subtasks],
            "execution_order": self.execution_order,
            "estimated_duration_ms": self.estimated_duration_ms,
        }
