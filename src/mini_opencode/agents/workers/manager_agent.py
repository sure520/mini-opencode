"""Manager Agent for multi-agent coordination.

The Manager Agent is responsible for:
1. Task decomposition - Breaking down user requests into subtasks
2. Topological sorting - Computing task execution order
3. Result aggregation - Collecting worker results and generating responses
"""

from collections import defaultdict
from datetime import datetime
from typing import Any
from uuid import uuid4

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool, tool

from mini_opencode.agents.types import (
    CoordinationPhase,
    CoordinationState,
    ParentTask,
    SubTask,
    TaskPlan,
    TaskStatus,
    TaskType,
    WorkerResult,
)
from mini_opencode.models import init_chat_model

logger = structlog.get_logger()


MANAGER_SYSTEM_PROMPT = """You are a Manager Agent responsible for coordinating a team of specialized AI workers.

Your role is to:
1. Analyze user requests and break them down into manageable subtasks
2. Assign each subtask to the appropriate worker type (coder, debugger, tester)
3. Identify dependencies between tasks to determine execution order
4. Aggregate results from workers into a coherent final response

## Worker Types
- **coder**: Handles code generation, file creation, and implementation tasks
- **debugger**: Handles error analysis, bug fixing, and code repair
- **tester**: Handles test creation and execution (future)
- **reviewer**: Handles code review and quality checks (future)

## Task Decomposition Guidelines
1. Keep tasks atomic and focused on a single responsibility
2. Identify clear dependencies (e.g., "implement function" must complete before "write tests for function")
3. Tasks that can run in parallel should have no dependencies between them
4. For simple requests, a single task may be sufficient

When decomposing tasks, output a JSON structure with the following format:
{
    "subtasks": [
        {
            "task_id": "unique_id",
            "task_type": "coder|debugger|tester|reviewer",
            "description": "Clear description of what needs to be done",
            "dependencies": ["task_id_of_dependency", ...]
        }
    ]
}
"""


class ManagerAgent:
    """Manager Agent for coordinating multi-agent workflows.

    The Manager is responsible for task decomposition, worker coordination,
    and result aggregation.

    Attributes:
        model: The language model for reasoning.
        workers: Dict mapping worker_id to worker instances.
    """

    def __init__(
        self,
        model: Any = None,
        tools: list[BaseTool] | None = None,
    ):
        """Initialize the Manager Agent.

        Args:
            model: Language model to use. If None, uses default.
            tools: Additional tools for the manager.
        """
        self.model = model or init_chat_model()
        self.tools = tools or []
        self.workers: dict[str, Any] = {}
        self._logger = logger.bind(agent="manager")

    def register_worker(self, worker_id: str, worker: Any) -> None:
        """Register a worker with the manager.

        Args:
            worker_id: Unique identifier for the worker.
            worker: The worker instance.
        """
        self.workers[worker_id] = worker
        self._logger.info("worker_registered", worker_id=worker_id)

    def unregister_worker(self, worker_id: str) -> bool:
        """Unregister a worker from the manager.

        Args:
            worker_id: The worker to unregister.

        Returns:
            True if worker was removed, False if not found.
        """
        if worker_id in self.workers:
            del self.workers[worker_id]
            self._logger.info("worker_unregistered", worker_id=worker_id)
            return True
        return False

    async def decompose_task(
        self,
        user_request: str,
        context: dict[str, Any] | None = None,
    ) -> TaskPlan:
        """Decompose a user request into a task plan.

        Args:
            user_request: The original user request.
            context: Additional context for decomposition.

        Returns:
            TaskPlan with subtasks and execution order.
        """
        self._logger.info("decomposing_task", request_length=len(user_request))

        # Create parent task
        parent_task = ParentTask(
            task_id=f"parent_{uuid4().hex[:8]}",
            original_request=user_request,
        )

        # Build decomposition prompt
        context_str = ""
        if context:
            context_items = [f"- {k}: {v}" for k, v in context.items()]
            context_str = "\n".join(context_items)

        decomposition_prompt = f"""Please analyze this user request and decompose it into subtasks.

## User Request
{user_request}

## Additional Context
{context_str if context_str else "No additional context."}

## Instructions
1. Analyze what needs to be done
2. Break it into atomic subtasks
3. Assign each subtask to the appropriate worker type
4. Identify dependencies between tasks
5. Return a JSON structure with the subtasks

Remember: For simple requests, a single task may be sufficient.
"""

        # Invoke model for decomposition
        messages = [
            SystemMessage(content=MANAGER_SYSTEM_PROMPT),
            HumanMessage(content=decomposition_prompt),
        ]

        response = await self.model.ainvoke(messages)

        # Parse response to extract subtasks
        subtasks = self._parse_decomposition_response(response.content, parent_task)

        # Compute execution order
        execution_order = self._compute_execution_order(subtasks)

        # Update parent task with subtask IDs
        parent_task.subtasks = [t.task_id for t in subtasks]

        plan = TaskPlan(
            plan_id=f"plan_{uuid4().hex[:8]}",
            parent_task=parent_task,
            subtasks=subtasks,
            execution_order=execution_order,
        )

        self._logger.info(
            "task_decomposed",
            subtask_count=len(subtasks),
            parallel_groups=len(execution_order),
        )

        return plan

    def _parse_decomposition_response(
        self,
        content: str,
        parent_task: ParentTask,
    ) -> list[SubTask]:
        """Parse the model response to extract subtasks.

        Args:
            content: The model response content.
            parent_task: The parent task for reference.

        Returns:
            List of SubTask instances.
        """
        import json
        import re

        subtasks = []

        # Try to extract JSON from the response
        json_match = re.search(r'\{[\s\S]*"subtasks"[\s\S]*\}', content)

        if json_match:
            try:
                data = json.loads(json_match.group())
                for task_data in data.get("subtasks", []):
                    task_type_str = task_data.get("task_type", "coder")
                    try:
                        task_type = TaskType(task_type_str)
                    except ValueError:
                        task_type = TaskType.CODER

                    subtask = SubTask(
                        task_id=task_data.get(
                            "task_id", f"task_{uuid4().hex[:8]}"
                        ),
                        task_type=task_type,
                        description=task_data.get("description", ""),
                        dependencies=task_data.get("dependencies", []),
                    )
                    subtasks.append(subtask)
            except json.JSONDecodeError:
                self._logger.warning("failed_to_parse_json", content=content[:200])

        # If no subtasks were parsed, create a default one
        if not subtasks:
            subtasks.append(
                SubTask(
                    task_id=f"task_{uuid4().hex[:8]}",
                    task_type=TaskType.CODER,
                    description=parent_task.original_request,
                    dependencies=[],
                )
            )

        return subtasks

    def _compute_execution_order(
        self,
        subtasks: list[SubTask],
    ) -> list[list[str]]:
        """Compute execution order using topological sort.

        Groups tasks that can be executed in parallel.

        Args:
            subtasks: List of subtasks with dependencies.

        Returns:
            List of groups, where each group can run in parallel.
        """
        task_map = {t.task_id: t for t in subtasks}
        in_degree: dict[str, int] = defaultdict(int)
        dependents: dict[str, list[str]] = defaultdict(list)

        # Build dependency graph
        for task in subtasks:
            for dep in task.dependencies:
                if dep in task_map:
                    dependents[dep].append(task.task_id)
                    in_degree[task.task_id] += 1

        # Initialize tasks with no dependencies
        execution_order = []
        current_group = [
            t.task_id for t in subtasks if in_degree[t.task_id] == 0
        ]

        while current_group:
            execution_order.append(current_group)
            next_group = []

            for task_id in current_group:
                for dependent in dependents[task_id]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        next_group.append(dependent)

            current_group = next_group

        return execution_order

    async def coordinate(
        self,
        plan: TaskPlan,
        state: dict[str, Any],
    ) -> CoordinationState:
        """Coordinate task execution based on the plan.

        Args:
            plan: The task plan to execute.
            state: Current multi-agent state.

        Returns:
            Updated CoordinationState.
        """
        coordination = state.get("coordination", CoordinationState())

        if coordination.phase == CoordinationPhase.COMPLETED:
            return coordination

        # Get completed tasks
        completed_tasks = {
            t.task_id for t in plan.subtasks
            if t.status == TaskStatus.COMPLETED
        }

        # Check if all tasks are done
        all_done = all(
            t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
            for t in plan.subtasks
        )

        if all_done:
            coordination.phase = CoordinationPhase.AGGREGATING
            return coordination

        # Find tasks ready to execute
        ready_tasks = plan.get_ready_tasks(completed_tasks)

        if ready_tasks and coordination.phase == CoordinationPhase.PLANNING:
            coordination.phase = CoordinationPhase.EXECUTING

        # Update parallel groups with ready task IDs
        coordination.parallel_groups = [[t.task_id for t in ready_tasks]]
        coordination.completed_count = len(completed_tasks)
        coordination.failed_count = len([
            t for t in plan.subtasks if t.status == TaskStatus.FAILED
        ])

        return coordination

    async def assign_task(
        self,
        task: SubTask,
    ) -> str | None:
        """Assign a task to an appropriate worker.

        Args:
            task: The task to assign.

        Returns:
            Worker ID if assigned, None if no suitable worker.
        """
        # Find workers of the matching type
        for worker_id, worker in self.workers.items():
            if hasattr(worker, 'worker_type'):
                if worker.worker_type == task.task_type.value:
                    task.mark_running(worker_id)
                    self._logger.info(
                        "task_assigned",
                        task_id=task.task_id,
                        worker_id=worker_id,
                    )
                    return worker_id

        self._logger.warning(
            "no_suitable_worker",
            task_id=task.task_id,
            task_type=task.task_type.value,
        )
        return None

    async def aggregate_results(
        self,
        plan: TaskPlan,
        results: dict[str, WorkerResult],
    ) -> str:
        """Aggregate results from all workers into a final response.

        Args:
            plan: The executed task plan.
            results: Dict mapping task_id to WorkerResult.

        Returns:
            Aggregated response string.
        """
        self._logger.info(
            "aggregating_results",
            result_count=len(results),
        )

        # Build aggregation prompt
        results_summary = []
        for task in plan.subtasks:
            result = results.get(task.task_id)
            status = "completed" if result and result.success else "failed"
            output = result.output if result else "No output"
            error = result.error if result else None

            summary = f"""### Task: {task.description}
- Status: {status}
- Output: {output[:500] if output else 'N/A'}"""
            if error:
                summary += f"\n- Error: {error}"

            results_summary.append(summary)

        aggregation_prompt = f"""Please synthesize the results from all completed tasks into a coherent response for the user.

## Original Request
{plan.parent_task.original_request}

## Task Results
{chr(10).join(results_summary)}

## Instructions
1. Summarize what was accomplished
2. Highlight any errors or issues that need attention
3. Provide a clear, user-friendly response
"""

        messages = [
            SystemMessage(content="You are a helpful assistant summarizing task results."),
            HumanMessage(content=aggregation_prompt),
        ]

        response = await self.model.ainvoke(messages)

        # Mark parent task as completed
        plan.parent_task.completed_at = datetime.now()

        return str(response.content)

    def get_worker_stats(self) -> dict[str, Any]:
        """Get statistics about registered workers.

        Returns:
            Dict with worker statistics.
        """
        worker_types: dict[str, int] = defaultdict(int)
        for worker in self.workers.values():
            if hasattr(worker, 'worker_type'):
                worker_types[worker.worker_type] += 1

        return {
            "total_workers": len(self.workers),
            "worker_types": dict(worker_types),
            "worker_ids": list(self.workers.keys()),
        }
