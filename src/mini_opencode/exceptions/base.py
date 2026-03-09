"""Base exception classes for mini-OpenCode."""


class BaseError(Exception):
    """Base exception class for all mini-OpenCode errors."""
    pass


class ToolError(BaseError):
    """Base exception class for tool-related errors."""
    pass


class AgentError(BaseError):
    """Base exception class for agent-related errors."""
    pass
