"""Coder Worker for code generation tasks."""

from datetime import datetime
from typing import Any

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from mini_opencode.agents.types import SubTask, WorkerResult
from mini_opencode.agents.workers.base_worker import BaseWorker
from mini_opencode.tools import edit_tool, grep_tool, ls_tool, read_tool, write_tool

logger = structlog.get_logger()


CODER_SYSTEM_PROMPT = """You are a Coder Worker, a specialized AI agent focused on code generation and implementation.

## Your Responsibilities
1. Write clean, well-documented code following best practices
2. Create new files when needed
3. Modify existing code as required
4. Follow the project's coding style and conventions

## Available Tools
- **read**: Read file contents to understand existing code
- **write**: Create new files or overwrite existing ones
- **edit**: Make targeted edits to existing files
- **grep**: Search for patterns in files
- **ls**: List directory contents

## Guidelines
1. Always read existing files before modifying them
2. Use descriptive variable and function names
3. Add appropriate comments and docstrings
4. Handle edge cases and errors gracefully
5. Follow the DRY (Don't Repeat Yourself) principle

When you complete a task, provide a clear summary of:
- What files were created or modified
- Key changes made
- Any assumptions or decisions you made
"""


class CoderWorker(BaseWorker):
    """Worker specialized in code generation tasks.

    The Coder Worker handles tasks like:
    - Creating new files
    - Implementing functions and classes
    - Modifying existing code
    - Writing tests (basic)

    Attributes:
        worker_id: Unique identifier for this worker.
        model: Language model for code generation.
        tools: List of coding-related tools.
    """

    def __init__(
        self,
        model: Any = None,
        tools: list[BaseTool] | None = None,
        worker_id: str | None = None,
    ):
        """Initialize the Coder Worker.

        Args:
            model: Language model to use. If None, uses default.
            tools: Additional tools. Default coding tools are always included.
            worker_id: Unique ID. If None, generates a UUID.
        """
        # Default coding tools
        default_tools: list[BaseTool] = [
            read_tool,
            write_tool,
            edit_tool,
            grep_tool,
            ls_tool,
        ]

        # Combine with any additional tools
        all_tools = default_tools + (tools or [])

        super().__init__(
            worker_type="coder",
            tools=all_tools,
            model=model,
            worker_id=worker_id,
        )

    async def execute(
        self,
        task: SubTask,
        context: dict[str, Any],
    ) -> WorkerResult:
        """Execute a code generation task.

        Args:
            task: The coding task to execute.
            context: Shared context from the multi-agent state.

        Returns:
            WorkerResult with execution outcome.
        """
        start_time = datetime.now()
        self._logger.info(
            "executing_task",
            task_id=task.task_id,
            description=task.description[:100],
        )

        try:
            # Build the task prompt
            task_prompt = self._build_coder_prompt(task, context)

            # Invoke model with tools
            messages = [HumanMessage(content=task_prompt)]
            tool_calls_made: list[dict[str, Any]] = []
            output_content = ""
            max_iterations = 10
            iteration = 0

            while iteration < max_iterations:
                iteration += 1

                response = await self._invoke_model(
                    messages,
                    system_prompt=CODER_SYSTEM_PROMPT,
                )

                # Check if model wants to use tools
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    for tool_call in response.tool_calls:
                        tool_result = await self._execute_tool_call(tool_call)
                        tool_calls_made.append({
                            "tool": tool_call.get("name", "unknown"),
                            "args": tool_call.get("args", {}),
                            "result": tool_result[:500] if tool_result else None,
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

            self._logger.info(
                "task_completed",
                task_id=task.task_id,
                tool_calls=len(tool_calls_made),
                iterations=iteration,
            )

            return self._create_result(
                task=task,
                success=True,
                output=output_content,
                tool_calls=tool_calls_made,
                start_time=start_time,
            )

        except Exception as e:
            self._logger.error(
                "task_failed",
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

    def _build_coder_prompt(
        self,
        task: SubTask,
        context: dict[str, Any],
    ) -> str:
        """Build a prompt specific to coding tasks.

        Args:
            task: The coding task.
            context: Additional context.

        Returns:
            Formatted prompt string.
        """
        context_str = ""
        if context:
            # Extract relevant context for coding
            project_root = context.get("project_root", "")
            code_style = context.get("code_style", "")
            related_files = context.get("related_files", [])

            if project_root:
                context_str += f"- Project root: {project_root}\n"
            if code_style:
                context_str += f"- Code style: {code_style}\n"
            if related_files:
                context_str += f"- Related files: {', '.join(related_files)}\n"

        # Include task-specific context
        task_context = task.context
        if task_context:
            for k, v in task_context.items():
                context_str += f"- {k}: {v}\n"

        return f"""## Coding Task
{task.description}

## Context
{context_str if context_str else "No additional context."}

## Instructions
1. First, use the `ls` or `grep` tool if you need to explore the codebase
2. Use `read` to examine any relevant existing files
3. Write your implementation using `write` or `edit`
4. Verify your changes are correct
5. Provide a summary of what you did

Please proceed with the implementation.
"""
