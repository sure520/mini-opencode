"""Base worker class for multi-agent architecture."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import uuid4

import structlog
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool

from mini_opencode.agents.types import SubTask, TaskStatus, WorkerResult
from mini_opencode.models import init_chat_model

logger = structlog.get_logger()


class BaseWorker(ABC):
    """Abstract base class for worker agents.

    Workers are specialized agents that handle specific types of tasks
    (coding, debugging, testing, etc.) under the coordination of the Manager.

    Attributes:
        worker_id: Unique identifier for this worker.
        worker_type: Type of worker (coder, debugger, etc.).
        model: The language model used by this worker.
        tools: List of tools available to this worker.
    """

    def __init__(
        self,
        worker_type: str,
        tools: list[BaseTool] | None = None,
        model: Any = None,
        worker_id: str | None = None,
    ):
        """Initialize the worker.

        Args:
            worker_type: Type identifier for this worker.
            tools: List of tools available to this worker.
            model: Language model to use. If None, uses default.
            worker_id: Unique ID. If None, generates a UUID.
        """
        self.worker_id = worker_id or f"{worker_type}_{uuid4().hex[:8]}"
        self.worker_type = worker_type
        self.model = model or init_chat_model()
        self.tools = tools or []
        self._logger = logger.bind(worker_id=self.worker_id, worker_type=worker_type)

    @property
    def tool_names(self) -> list[str]:
        """Get names of available tools."""
        return [tool.name for tool in self.tools]

    @abstractmethod
    async def execute(
        self,
        task: SubTask,
        context: dict[str, Any],
    ) -> WorkerResult:
        """Execute a task and return the result.

        Args:
            task: The task to execute.
            context: Shared context from the multi-agent state.

        Returns:
            WorkerResult containing execution outcome.
        """
        pass

    def _create_result(
        self,
        task: SubTask,
        success: bool,
        output: str = "",
        error: str | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        start_time: datetime | None = None,
    ) -> WorkerResult:
        """Helper to create a WorkerResult.

        Args:
            task: The executed task.
            success: Whether execution succeeded.
            output: Output content.
            error: Error message if failed.
            tool_calls: List of tool calls made.
            start_time: Execution start time for duration calculation.

        Returns:
            WorkerResult instance.
        """
        execution_time_ms = 0
        if start_time:
            execution_time_ms = int(
                (datetime.now() - start_time).total_seconds() * 1000
            )

        return WorkerResult(
            worker_id=self.worker_id,
            task_id=task.task_id,
            success=success,
            output=output,
            error=error,
            tool_calls=tool_calls or [],
            execution_time_ms=execution_time_ms,
        )

    async def _invoke_model(
        self,
        messages: list[HumanMessage | AIMessage],
        system_prompt: str | None = None,
    ) -> AIMessage:
        """Invoke the model with messages.

        Args:
            messages: List of messages for the conversation.
            system_prompt: Optional system prompt to prepend.

        Returns:
            AIMessage response from the model.
        """
        model = self.model
        if self.tools:
            model = model.bind_tools(self.tools)

        if system_prompt:
            from langchain_core.messages import SystemMessage
            messages = [SystemMessage(content=system_prompt), *messages]

        response = await model.ainvoke(messages)
        return response

    def _build_task_prompt(self, task: SubTask, context: dict[str, Any]) -> str:
        """Build a prompt for the task.

        Args:
            task: The task to build prompt for.
            context: Additional context.

        Returns:
            Formatted prompt string.
        """
        context_str = ""
        if context:
            context_items = [f"- {k}: {v}" for k, v in context.items()]
            context_str = "\n".join(context_items)

        return f"""## Task
{task.description}

## Context
{context_str if context_str else "No additional context provided."}

## Instructions
Please complete the task above. If you need to use tools, call them appropriately.
Provide a clear summary of what you accomplished when done.
"""
