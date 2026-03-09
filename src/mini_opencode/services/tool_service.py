"""Tool service for managing tool-related operations."""

from typing import Dict, Any, Optional, Callable
from langchain.tools import ToolRuntime


class ToolService:
    """Service for managing tool calls and executions."""

    def __init__(self):
        """Initialize the tool service."""
        self._tools: Dict[str, Callable] = {}

    def register_tool(self, name: str, tool_func: Callable) -> None:
        """Register a tool with the service.

        Args:
            name: The name of the tool.
            tool_func: The tool function to register.
        """
        self._tools[name] = tool_func

    def get_tool(self, name: str) -> Optional[Callable]:
        """Get a tool by name.

        Args:
            name: The name of the tool.

        Returns:
            Optional[Callable]: The tool function if found, None otherwise.
        """
        return self._tools.get(name)

    def execute_tool(self, runtime: ToolRuntime, tool_name: str, **kwargs) -> str:
        """Execute a tool with the given arguments.

        Args:
            runtime: The tool runtime context.
            tool_name: The name of the tool to execute.
            **kwargs: Arguments to pass to the tool.

        Returns:
            str: The tool execution result.
        """
        tool_func = self.get_tool(tool_name)
        if not tool_func:
            return f"Error: Tool '{tool_name}' not found."

        try:
            result = tool_func(runtime, **kwargs)
            return result
        except Exception as e:
            return f"Error executing tool '{tool_name}': {str(e)}"

    def list_tools(self) -> list[str]:
        """List all registered tools.

        Returns:
            list[str]: List of tool names.
        """
        return list(self._tools.keys())
