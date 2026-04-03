"""Debugger Worker for code analysis and repair tasks."""

from datetime import datetime
from typing import Any

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from mini_opencode.agents.types import SubTask, WorkerResult
from mini_opencode.agents.workers.base_worker import BaseWorker
from mini_opencode.tools import bash_tool, edit_tool, grep_tool, ls_tool, read_tool

logger = structlog.get_logger()


DEBUGGER_SYSTEM_PROMPT = """You are a Debugger Worker, a specialized AI agent focused on code analysis and bug fixing.

## Your Responsibilities
1. Analyze error messages and stack traces
2. Identify the root cause of bugs
3. Propose and implement fixes
4. Verify fixes by running tests when possible

## Available Tools
- **read**: Read file contents to analyze code
- **edit**: Make targeted fixes to code
- **grep**: Search for patterns across files
- **ls**: List directory contents
- **bash**: Run commands to test fixes or get more information

## Debugging Strategy
1. **Understand the Error**: Carefully read the error message and stack trace
2. **Locate the Problem**: Use grep and read to find the relevant code
3. **Analyze the Root Cause**: Determine why the error is occurring
4. **Implement the Fix**: Use edit to make minimal, targeted changes
5. **Verify the Fix**: Run tests or the command that caused the error

## Guidelines
1. Make minimal changes - fix only what's broken
2. Don't introduce new features while debugging
3. Add error handling where appropriate
4. Document your fix in code comments
5. If unsure, explain your reasoning before making changes

When you complete a task, provide:
- Root cause analysis
- What was fixed
- How to verify the fix
"""


class DebuggerWorker(BaseWorker):
    """Worker specialized in code debugging and repair.

    The Debugger Worker handles tasks like:
    - Analyzing error messages and stack traces
    - Identifying root causes of bugs
    - Implementing minimal fixes
    - Running tests to verify fixes

    Attributes:
        worker_id: Unique identifier for this worker.
        model: Language model for debugging.
        tools: List of debugging-related tools.
    """

    def __init__(
        self,
        model: Any = None,
        tools: list[BaseTool] | None = None,
        worker_id: str | None = None,
    ):
        """Initialize the Debugger Worker.

        Args:
            model: Language model to use. If None, uses default.
            tools: Additional tools. Default debugging tools are always included.
            worker_id: Unique ID. If None, generates a UUID.
        """
        # Default debugging tools
        default_tools: list[BaseTool] = [
            read_tool,
            edit_tool,
            grep_tool,
            ls_tool,
            bash_tool,
        ]

        # Combine with any additional tools
        all_tools = default_tools + (tools or [])

        super().__init__(
            worker_type="debugger",
            tools=all_tools,
            model=model,
            worker_id=worker_id,
        )

    async def execute(
        self,
        task: SubTask,
        context: dict[str, Any],
    ) -> WorkerResult:
        """Execute a debugging task.

        Args:
            task: The debugging task to execute.
            context: Shared context from the multi-agent state.

        Returns:
            WorkerResult with execution outcome.
        """
        start_time = datetime.now()
        self._logger.info(
            "executing_debug_task",
            task_id=task.task_id,
            description=task.description[:100],
        )

        try:
            # Build the debugging prompt
            task_prompt = self._build_debugger_prompt(task, context)

            # Invoke model with tools
            messages = [HumanMessage(content=task_prompt)]
            tool_calls_made: list[dict[str, Any]] = []
            output_content = ""
            max_iterations = 15  # More iterations for debugging
            iteration = 0

            while iteration < max_iterations:
                iteration += 1

                response = await self._invoke_model(
                    messages,
                    system_prompt=DEBUGGER_SYSTEM_PROMPT,
                )

                # Check if model wants to use tools
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    for tool_call in response.tool_calls:
                        tool_result = await self._execute_tool_call(tool_call)
                        tool_calls_made.append({
                            "tool": tool_call.get("name", "unknown"),
                            "args": tool_call.get("args", {}),
                            "result": tool_result[:1000] if tool_result else None,
                        })

                        # Add tool result to messages for next iteration
                        from langchain_core.messages import ToolMessage
                        messages.append(response)
                        messages.append(ToolMessage(
                            content=tool_result,
                            tool_call_id=tool_call.get("id", ""),
                        ))
                else:
                    # No more tool calls, we have the final response
                    output_content = str(response.content)
                    break

            # Determine success based on output
            success = self._analyze_debugging_result(output_content, tool_calls_made)

            self._logger.info(
                "debug_task_completed",
                task_id=task.task_id,
                tool_calls=len(tool_calls_made),
                iterations=iteration,
                success=success,
            )

            return self._create_result(
                task=task,
                success=success,
                output=output_content,
                tool_calls=tool_calls_made,
                start_time=start_time,
            )

        except Exception as e:
            self._logger.error(
                "debug_task_failed",
                task_id=task.task_id,
                error=str(e),
            )
            return self._create_result(
                task=task,
                success=False,
                error=str(e),
                start_time=start_time,
            )

    async def _execute_tool_call(
        self,
        tool_call: dict[str, Any],
    ) -> str:
        """Execute a single tool call.

        Args:
            tool_call: The tool call dict from the model.

        Returns:
            Tool execution result as string.
        """
        tool_name = tool_call.get("name", "")
        tool_args = tool_call.get("args", {})

        for tool in self.tools:
            if tool.name == tool_name:
                try:
                    result = await tool.ainvoke(tool_args)
                    return str(result)
                except Exception as e:
                    return f"Error executing {tool_name}: {str(e)}"

        return f"Tool '{tool_name}' not found"

    def _build_debugger_prompt(
        self,
        task: SubTask,
        context: dict[str, Any],
    ) -> str:
        """Build a prompt specific to debugging tasks.

        Args:
            task: The debugging task.
            context: Additional context.

        Returns:
            Formatted prompt string.
        """
        context_str = ""
        if context:
            # Extract relevant context for debugging
            error_message = context.get("error_message", "")
            stack_trace = context.get("stack_trace", "")
            test_output = context.get("test_output", "")
            affected_files = context.get("affected_files", [])

            if error_message:
                context_str += f"## Error Message\n```\n{error_message}\n```\n\n"
            if stack_trace:
                context_str += f"## Stack Trace\n```\n{stack_trace}\n```\n\n"
            if test_output:
                context_str += f"## Test Output\n```\n{test_output}\n```\n\n"
            if affected_files:
                context_str += f"## Affected Files\n{', '.join(affected_files)}\n\n"

        # Include task-specific context
        task_context = task.context
        if task_context:
            if task_context.get("error_type"):
                context_str += f"- Error Type: {task_context['error_type']}\n"
            if task_context.get("file_path"):
                context_str += f"- File: {task_context['file_path']}\n"
            if task_context.get("line_number"):
                context_str += f"- Line: {task_context['line_number']}\n"

        return f"""## Debugging Task
{task.description}

{context_str if context_str else "## Context\nNo additional context provided."}

## Instructions
1. First, analyze the error information above
2. Use `grep` and `read` to locate the problematic code
3. Identify the root cause of the issue
4. Use `edit` to implement a minimal fix
5. If possible, use `bash` to run tests or verify the fix
6. Provide a summary of:
   - What was wrong (root cause)
   - What you fixed
   - How to verify the fix

Please proceed with the debugging.
"""

    def _analyze_debugging_result(
        self,
        output: str,
        tool_calls: list[dict[str, Any]],
    ) -> bool:
        """Analyze whether debugging was successful.

        Args:
            output: The final output from the model.
            tool_calls: List of tool calls made.

        Returns:
            True if debugging appears successful.
        """
        # Check for positive indicators in output
        positive_indicators = [
            "fixed",
            "resolved",
            "corrected",
            "repair",
            "successfully",
            "issue has been",
            "bug has been",
        ]

        # Check for negative indicators
        negative_indicators = [
            "unable to fix",
            "cannot fix",
            "failed to",
            "could not determine",
            "need more information",
        ]

        output_lower = output.lower()

        # Check for edit tool calls (indicates fix was applied)
        has_edit = any(tc.get("tool") == "edit" for tc in tool_calls)

        # Positive if has edit and positive language, no negative language
        has_positive = any(ind in output_lower for ind in positive_indicators)
        has_negative = any(ind in output_lower for ind in negative_indicators)

        if has_negative:
            return False

        if has_edit and has_positive:
            return True

        # Default to True if edit was made
        return has_edit


class TesterWorker(BaseWorker):
    """Worker specialized in running tests (placeholder for future).

    This worker will handle:
    - Running unit tests
    - Running integration tests
    - Analyzing test results
    """

    def __init__(
        self,
        model: Any = None,
        tools: list[BaseTool] | None = None,
        worker_id: str | None = None,
    ):
        """Initialize the Tester Worker."""
        default_tools: list[BaseTool] = [
            bash_tool,
            read_tool,
            grep_tool,
        ]

        all_tools = default_tools + (tools or [])

        super().__init__(
            worker_type="tester",
            tools=all_tools,
            model=model,
            worker_id=worker_id,
        )

    async def execute(
        self,
        task: SubTask,
        context: dict[str, Any],
    ) -> WorkerResult:
        """Execute a testing task.

        Args:
            task: The testing task to execute.
            context: Shared context from the multi-agent state.

        Returns:
            WorkerResult with test outcomes.
        """
        start_time = datetime.now()
        self._logger.info(
            "executing_test_task",
            task_id=task.task_id,
        )

        # TODO: Implement test execution logic
        # For now, return a placeholder result
        return self._create_result(
            task=task,
            success=True,
            output="Test execution not yet implemented",
            start_time=start_time,
        )
