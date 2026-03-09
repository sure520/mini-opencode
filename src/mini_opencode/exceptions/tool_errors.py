"""Tool execution exception classes for mini-OpenCode."""

from .base import ToolError


class ToolExecutionError(ToolError):
    """Exception raised when tool execution fails."""
    pass


class ToolTimeoutError(ToolError):
    """Exception raised when tool execution times out."""
    pass


class ToolNotFoundError(ToolError):
    """Exception raised when a tool is not found."""
    pass


class ToolValidationError(ToolError):
    """Exception raised when tool parameters are invalid."""
    pass
