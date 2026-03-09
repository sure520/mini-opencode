"""Agent-related exception classes for mini-OpenCode."""

from .base import AgentError


class AgentInitError(AgentError):
    """Exception raised when agent initialization fails."""
    pass


class AgentRuntimeError(AgentError):
    """Exception raised when agent runtime fails."""
    pass


class AgentStateError(AgentError):
    """Exception raised when agent state is invalid."""
    pass


class AgentConfigError(AgentError):
    """Exception raised when agent configuration is invalid."""
    pass
