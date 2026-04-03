"""DAG Workflow for multi-agent coding automation.

This module implements the "Plan-Code-Test-Fix" workflow using LangGraph.
The workflow supports:
1. Task planning and decomposition
2. Code generation by Coder Worker
3. Test execution by Tester Worker
4. Automatic error fixing with iteration limit

Workflow DAG:
    planner -> coder -> tester -> [aggregator | fixer]
                                     ^           |
                                     |___________|
                                    (max 3 iterations)
"""

from typing import Any, Literal

import structlog
from langgraph.graph import END, StateGraph

from mini_opencode.agents.state import MultiAgentState
from mini_opencode.agents.types import (
    CoordinationPhase,
    CoordinationState,
    SubTask,
    TaskPlan,
    TaskStatus,
    TaskType,
    WorkerResult,
)
from mini_opencode.agents.workers import (
    BaseWorker,
    CoderWorker,
    DebuggerWorker,
    ManagerAgent,
    TesterWorker,
)
from mini_opencode.models import init_chat_model

logger = structlog.get_logger()


# --- Workflow Constants ---
MAX_FIX_ITERATIONS = 3
WORKFLOW_TIMEOUT_SECONDS = 300


# --- Node Functions ---


async def planner_node(state: dict[str, Any]) -> dict[str, Any]:
    """Plan and decompose the user request into subtasks.

    This node:
    1. Analyzes the user's request
    2. Breaks it down into atomic subtasks
    3. Assigns task types (coder, tester, debugger)
    4. Computes execution order

    Args:
        state: Current workflow state.

    Returns:
        Updated state with task plan.
    """
    log = logger.bind(node="planner")
    log.info("planner_started")

    # Get the latest user message
    messages = state.get("messages", [])
    if not messages:
        log.warning("no_messages_found")
        return state

    user_request = ""
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            user_request = msg.content
            break
        elif isinstance(msg, dict) and msg.get("type") == "human":
            user_request = msg.get("content", "")
            break

    if not user_request:
        log.warning("no_user_request_found")
        return state

    # Initialize manager and decompose task
    model = init_chat_model()
    manager = ManagerAgent(model=model)

    context = {
        "memory_context": state.get("memory_context", ""),
        "shared_context": state.get("shared_context", {}),
    }

    plan = await manager.decompose_task(user_request, context)

    # Update state
    coordination = state.get("coordination", CoordinationState())
    coordination.phase = CoordinationPhase.EXECUTING

    log.info(
        "planning_complete",
        subtask_count=len(plan.subtasks),
        execution_order=plan.execution_order,
    )

    return {
        **state,
        "parent_task": plan.parent_task,
        "subtasks": plan.subtasks,
        "coordination": coordination,
        "shared_context": {
            **state.get("shared_context", {}),
            "task_plan": plan.to_dict(),
        },
    }


async def coder_node(state: dict[str, Any]) -> dict[str, Any]:
    """Execute code generation tasks.

    This node:
    1. Finds pending CODER type tasks
    2. Executes them using CoderWorker
    3. Updates task status and results

    Args:
        state: Current workflow state.

    Returns:
        Updated state with coder results.
    """
    log = logger.bind(node="coder")
    log.info("coder_started")

    subtasks: list[SubTask] = state.get("subtasks", [])
    worker_results: dict[str, WorkerResult] = state.get("worker_results", {})

    # Find pending coder tasks
    coder_tasks = [
        task for task in subtasks
        if task.task_type == TaskType.CODER and task.status == TaskStatus.PENDING
    ]

    if not coder_tasks:
        log.info("no_coder_tasks")
        return state

    # Initialize coder worker
    model = init_chat_model()
    coder = CoderWorker(model=model, tools=[])
    worker_id = "coder_worker_1"

    # Execute each coder task
    for task in coder_tasks:
        log.info("executing_coder_task", task_id=task.task_id)

        # Build context from previous results and shared context
        context = {
            "shared_context": state.get("shared_context", {}),
            "previous_results": {
                tid: r.to_dict() for tid, r in worker_results.items()
            },
        }

        try:
            result = await coder.execute(task, context)
            worker_results[task.task_id] = result

            if result.success:
                task.mark_completed(result.output)
            else:
                task.mark_failed(result.error or "Unknown error")

        except Exception as e:
            log.error("coder_task_failed", task_id=task.task_id, error=str(e))
            task.mark_failed(str(e))
            worker_results[task.task_id] = WorkerResult(
                worker_id=worker_id,
                task_id=task.task_id,
                success=False,
                error=str(e),
            )

    log.info("coder_complete", tasks_processed=len(coder_tasks))

    return {
        **state,
        "subtasks": subtasks,
        "worker_results": worker_results,
    }


async def tester_node(state: dict[str, Any]) -> dict[str, Any]:
    """Execute test tasks and validate code.

    This node:
    1. Finds pending TESTER type tasks
    2. Runs tests using TesterWorker
    3. Updates test results

    Args:
        state: Current workflow state.

    Returns:
        Updated state with test results.
    """
    log = logger.bind(node="tester")
    log.info("tester_started")

    subtasks: list[SubTask] = state.get("subtasks", [])
    worker_results: dict[str, WorkerResult] = state.get("worker_results", {})

    # Find pending tester tasks
    tester_tasks = [
        task for task in subtasks
        if task.task_type == TaskType.TESTER and task.status == TaskStatus.PENDING
    ]

    if not tester_tasks:
        log.info("no_tester_tasks")
        # No explicit test tasks - run automatic validation
        # Check if there are any coder results that need validation
        coder_results = [
            r for tid, r in worker_results.items()
            if any(t.task_id == tid and t.task_type == TaskType.CODER 
                   for t in subtasks)
        ]

        if coder_results:
            # Create synthetic test validation
            log.info("running_automatic_validation", coder_results=len(coder_results))
            # For now, assume code passes if coder was successful
            state["shared_context"]["tests_passed"] = all(r.success for r in coder_results)
            state["shared_context"]["test_errors"] = [
                r.error for r in coder_results if r.error
            ]
        else:
            state["shared_context"]["tests_passed"] = True
            state["shared_context"]["test_errors"] = []

        return state

    # Initialize tester worker
    model = init_chat_model()
    tester = TesterWorker(model=model, tools=[])
    worker_id = "tester_worker_1"

    test_errors = []

    # Execute each tester task
    for task in tester_tasks:
        log.info("executing_tester_task", task_id=task.task_id)

        context = {
            "shared_context": state.get("shared_context", {}),
            "previous_results": {
                tid: r.to_dict() for tid, r in worker_results.items()
            },
        }

        try:
            result = await tester.execute(task, context)
            worker_results[task.task_id] = result

            if result.success:
                task.mark_completed(result.output)
            else:
                task.mark_failed(result.error or "Test failed")
                test_errors.append(result.error or "Unknown test error")

        except Exception as e:
            log.error("tester_task_failed", task_id=task.task_id, error=str(e))
            task.mark_failed(str(e))
            test_errors.append(str(e))
            worker_results[task.task_id] = WorkerResult(
                worker_id=worker_id,
                task_id=task.task_id,
                success=False,
                error=str(e),
            )

    # Update test status in shared context
    all_tests_passed = len(test_errors) == 0
    state["shared_context"]["tests_passed"] = all_tests_passed
    state["shared_context"]["test_errors"] = test_errors

    log.info(
        "tester_complete",
        tasks_processed=len(tester_tasks),
        all_passed=all_tests_passed,
    )

    return {
        **state,
        "subtasks": subtasks,
        "worker_results": worker_results,
    }


async def fixer_node(state: dict[str, Any]) -> dict[str, Any]:
    """Fix errors identified by tester.

    This node:
    1. Analyzes test failures
    2. Uses DebuggerWorker to create fix tasks
    3. Increments iteration counter

    Args:
        state: Current workflow state.

    Returns:
        Updated state with fix attempts.
    """
    log = logger.bind(node="fixer")
    log.info("fixer_started")

    coordination: CoordinationState = state.get("coordination", CoordinationState())
    subtasks: list[SubTask] = state.get("subtasks", [])
    worker_results: dict[str, WorkerResult] = state.get("worker_results", {})

    # Increment iteration count
    coordination.increment_iteration()
    log.info(
        "fix_iteration",
        current=coordination.iteration_count,
        max=coordination.max_iterations,
    )

    # Get test errors
    test_errors = state.get("shared_context", {}).get("test_errors", [])

    if not test_errors:
        log.info("no_errors_to_fix")
        return {**state, "coordination": coordination}

    # Find failed tasks that need fixing
    failed_tasks = [
        task for task in subtasks
        if task.status == TaskStatus.FAILED
    ]

    # Initialize debugger worker
    model = init_chat_model()
    debugger = DebuggerWorker(model=model, tools=[])
    worker_id = "debugger_worker_1"

    # Create fix task for each failure
    for i, error in enumerate(test_errors[:3]):  # Limit to 3 errors per iteration
        fix_task_id = f"fix_{coordination.iteration_count}_{i}"

        fix_task = SubTask(
            task_id=fix_task_id,
            task_type=TaskType.DEBUGGER,
            description=f"Fix error: {error}",
        )

        log.info("executing_fix_task", task_id=fix_task_id, error=error[:100])

        context = {
            "shared_context": state.get("shared_context", {}),
            "error_to_fix": error,
            "previous_results": {
                tid: r.to_dict() for tid, r in worker_results.items()
            },
        }

        try:
            result = await debugger.execute(fix_task, context)
            worker_results[fix_task_id] = result

            if result.success:
                fix_task.mark_completed(result.output)
                # Reset related tasks to pending for re-execution
                for task in failed_tasks:
                    task.status = TaskStatus.PENDING
                    task.error = None
            else:
                fix_task.mark_failed(result.error or "Fix failed")

            subtasks.append(fix_task)

        except Exception as e:
            log.error("fix_task_failed", task_id=fix_task_id, error=str(e))
            fix_task.mark_failed(str(e))
            worker_results[fix_task_id] = WorkerResult(
                worker_id=worker_id,
                task_id=fix_task_id,
                success=False,
                error=str(e),
            )
            subtasks.append(fix_task)

    # Clear test errors for next iteration
    state["shared_context"]["test_errors"] = []
    state["shared_context"]["tests_passed"] = False

    log.info("fixer_complete", iteration=coordination.iteration_count)

    return {
        **state,
        "subtasks": subtasks,
        "worker_results": worker_results,
        "coordination": coordination,
    }


async def aggregator_node(state: dict[str, Any]) -> dict[str, Any]:
    """Aggregate results from all workers.

    This node:
    1. Collects all worker results
    2. Uses ManagerAgent to synthesize final response
    3. Marks workflow as completed

    Args:
        state: Current workflow state.

    Returns:
        Updated state with aggregated response.
    """
    log = logger.bind(node="aggregator")
    log.info("aggregator_started")

    subtasks: list[SubTask] = state.get("subtasks", [])
    worker_results: dict[str, WorkerResult] = state.get("worker_results", {})
    parent_task = state.get("parent_task")
    coordination: CoordinationState = state.get("coordination", CoordinationState())

    # Mark coordination as completed
    coordination.phase = CoordinationPhase.COMPLETED

    # Initialize manager for aggregation
    model = init_chat_model()
    manager = ManagerAgent(model=model)

    # Create TaskPlan from state
    if parent_task:
        plan = TaskPlan(
            plan_id="aggregation_plan",
            parent_task=parent_task,
            subtasks=subtasks,
        )

        try:
            final_response = await manager.aggregate_results(plan, worker_results)
        except Exception as e:
            log.error("aggregation_failed", error=str(e))
            final_response = f"任务完成，但结果汇总失败: {str(e)}"
    else:
        # No parent task - simple response
        successful = [r for r in worker_results.values() if r.success]
        failed = [r for r in worker_results.values() if not r.success]

        final_response = f"任务完成。成功: {len(successful)}, 失败: {len(failed)}"
        if failed:
            errors = [r.error for r in failed if r.error]
            final_response += f"\n错误: {', '.join(errors[:3])}"

    # Store aggregated response
    state["shared_context"]["final_response"] = final_response
    state["shared_context"]["workflow_completed"] = True

    log.info("aggregator_complete")

    return {
        **state,
        "coordination": coordination,
    }


# --- Conditional Edge Functions ---


def should_fix_or_complete(state: dict[str, Any]) -> Literal["fixer", "aggregator"]:
    """Determine if we should fix errors or complete workflow.

    Args:
        state: Current workflow state.

    Returns:
        "fixer" if tests failed and iterations remain, "aggregator" otherwise.
    """
    log = logger.bind(decision="should_fix_or_complete")

    # Check test results
    tests_passed = state.get("shared_context", {}).get("tests_passed", True)
    coordination: CoordinationState = state.get("coordination", CoordinationState())

    if tests_passed:
        log.info("tests_passed_routing_to_aggregator")
        return "aggregator"

    # Check iteration limit
    if not coordination.can_iterate():
        log.warning(
            "max_iterations_reached",
            iterations=coordination.iteration_count,
            max=coordination.max_iterations,
        )
        return "aggregator"

    log.info(
        "tests_failed_routing_to_fixer",
        iteration=coordination.iteration_count + 1,
    )
    return "fixer"


def should_continue_or_complete(
    state: dict[str, Any],
) -> Literal["tester", "aggregator"]:
    """Determine if we should continue testing or complete.

    Args:
        state: Current workflow state.

    Returns:
        "tester" for re-testing after fix, "aggregator" if done.
    """
    log = logger.bind(decision="should_continue_or_complete")

    coordination: CoordinationState = state.get("coordination", CoordinationState())

    # Check if we exceeded max iterations
    if not coordination.can_iterate():
        log.warning("max_iterations_exceeded_completing")
        return "aggregator"

    # After fix, go back to tester
    log.info("returning_to_tester")
    return "tester"


# --- Workflow Builder ---


def build_coding_workflow() -> StateGraph:
    """Build the DAG coding workflow.

    The workflow follows this pattern:
        planner -> coder -> tester -> [aggregator | fixer -> tester]

    Returns:
        Compiled LangGraph workflow.
    """
    log = logger.bind(workflow="coding_dag")
    log.info("building_workflow")

    # Create workflow with MultiAgentState
    workflow = StateGraph(MultiAgentState)

    # Add nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("coder", coder_node)
    workflow.add_node("tester", tester_node)
    workflow.add_node("fixer", fixer_node)
    workflow.add_node("aggregator", aggregator_node)

    # Set entry point
    workflow.set_entry_point("planner")

    # Define edges
    workflow.add_edge("planner", "coder")
    workflow.add_edge("coder", "tester")

    # Conditional edge: tester -> fixer (if tests fail) or aggregator (if pass)
    workflow.add_conditional_edges(
        "tester",
        should_fix_or_complete,
        {
            "fixer": "fixer",
            "aggregator": "aggregator",
        },
    )

    # Conditional edge: fixer -> tester (retry) or aggregator (max iterations)
    workflow.add_conditional_edges(
        "fixer",
        should_continue_or_complete,
        {
            "tester": "tester",
            "aggregator": "aggregator",
        },
    )

    # End node
    workflow.add_edge("aggregator", END)

    log.info("workflow_built_successfully")

    return workflow


def compile_coding_workflow():
    """Compile the coding workflow for execution.

    Returns:
        Compiled workflow ready for invocation.
    """
    workflow = build_coding_workflow()
    return workflow.compile()


# --- Workflow Runner ---


class CodingWorkflowRunner:
    """Runner for executing the coding workflow.

    This class provides a high-level interface for running the
    "Plan-Code-Test-Fix" workflow.

    Attributes:
        workflow: The compiled LangGraph workflow.
        max_iterations: Maximum fix iterations allowed.
    """

    def __init__(self, max_iterations: int = MAX_FIX_ITERATIONS):
        """Initialize the workflow runner.

        Args:
            max_iterations: Maximum fix iterations (default: 3).
        """
        self.workflow = compile_coding_workflow()
        self.max_iterations = max_iterations
        self._logger = logger.bind(runner="CodingWorkflowRunner")

    async def run(
        self,
        user_request: str,
        user_id: str = "default",
        memory_context: str = "",
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run the workflow for a user request.

        Args:
            user_request: The user's coding request.
            user_id: User identifier for memory isolation.
            memory_context: Context from long-term memory.
            config: Additional LangGraph configuration.

        Returns:
            Final workflow state with results.
        """
        from langchain_core.messages import HumanMessage

        self._logger.info(
            "workflow_started",
            user_id=user_id,
            request_length=len(user_request),
        )

        # Create initial state
        initial_state = MultiAgentState.create_initial(
            user_id=user_id,
            memory_context=memory_context,
        )

        # Add user message
        initial_state["messages"] = [HumanMessage(content=user_request)]

        # Set max iterations
        initial_state["coordination"] = CoordinationState(
            max_iterations=self.max_iterations
        )

        # Run workflow
        try:
            final_state = await self.workflow.ainvoke(
                initial_state,
                config=config or {},
            )

            self._logger.info(
                "workflow_completed",
                tasks_completed=len([
                    t for t in final_state.get("subtasks", [])
                    if t.status == TaskStatus.COMPLETED
                ]),
            )

            return final_state

        except Exception as e:
            self._logger.error("workflow_failed", error=str(e))
            raise

    def get_result(self, state: dict[str, Any]) -> str:
        """Extract the final response from workflow state.

        Args:
            state: The final workflow state.

        Returns:
            The aggregated response string.
        """
        return state.get("shared_context", {}).get(
            "final_response",
            "工作流执行完成，但未生成最终响应。",
        )

    def get_summary(self, state: dict[str, Any]) -> dict[str, Any]:
        """Get a summary of the workflow execution.

        Args:
            state: The final workflow state.

        Returns:
            Summary dict with statistics.
        """
        subtasks: list[SubTask] = state.get("subtasks", [])
        coordination: CoordinationState = state.get(
            "coordination", CoordinationState()
        )

        completed = [t for t in subtasks if t.status == TaskStatus.COMPLETED]
        failed = [t for t in subtasks if t.status == TaskStatus.FAILED]

        return {
            "total_tasks": len(subtasks),
            "completed_tasks": len(completed),
            "failed_tasks": len(failed),
            "fix_iterations": coordination.iteration_count,
            "max_iterations": coordination.max_iterations,
            "workflow_completed": state.get("shared_context", {}).get(
                "workflow_completed", False
            ),
            "tests_passed": state.get("shared_context", {}).get(
                "tests_passed", False
            ),
        }
