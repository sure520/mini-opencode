"""File-related exception classes for mini-OpenCode."""

from .base import ToolError


class FileNotFoundError(ToolError):
    """Exception raised when a file is not found."""
    pass


class PermissionError(ToolError):
    """Exception raised when there are permission issues with file operations."""
    pass


class FileReadError(ToolError):
    """Exception raised when reading a file fails."""
    pass


class FileWriteError(ToolError):
    """Exception raised when writing to a file fails."""
    pass


class InvalidPathError(ToolError):
    """Exception raised when an invalid path is provided."""
    pass
