"""Abstract base class for sandbox executors.

This module defines the SandboxExecutor interface that all sandbox
implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Any

from .types import ExecutionResult, SandboxConfig, SandboxInfo


class SandboxExecutor(ABC):
    """Abstract base class for sandbox executors.

    This class defines the interface for creating, managing, and executing
    commands within isolated sandbox environments.

    All implementations should handle:
    - Sandbox lifecycle (create, start, stop, destroy)
    - Command execution with timeout
    - File operations (copy to/from sandbox)
    - Resource isolation and limits
    """

    @abstractmethod
    async def create(self, config: SandboxConfig) -> SandboxInfo:
        """Create a new sandbox instance.

        Args:
            config: Configuration for the sandbox.

        Returns:
            SandboxInfo containing the sandbox ID and initial status.

        Raises:
            SandboxCreationError: If sandbox creation fails.
        """
        pass

    @abstractmethod
    async def execute(
        self,
        sandbox_id: str,
        command: str,
        timeout: int | None = None,
        working_dir: str | None = None,
    ) -> ExecutionResult:
        """Execute a command within the sandbox.

        Args:
            sandbox_id: The ID of the sandbox to execute in.
            command: The command to execute.
            timeout: Execution timeout in seconds (overrides config default).
            working_dir: Working directory for the command.

        Returns:
            ExecutionResult containing output, exit code, and status.

        Raises:
            SandboxNotFoundError: If the sandbox doesn't exist.
            SandboxExecutionError: If execution fails.
        """
        pass

    @abstractmethod
    async def copy_to(
        self,
        sandbox_id: str,
        src_path: str,
        dst_path: str,
    ) -> bool:
        """Copy a file or directory from host to sandbox.

        Args:
            sandbox_id: The sandbox to copy to.
            src_path: Source path on the host.
            dst_path: Destination path inside the sandbox.

        Returns:
            True if copy succeeded, False otherwise.

        Raises:
            SandboxNotFoundError: If the sandbox doesn't exist.
            FileNotFoundError: If source file doesn't exist.
        """
        pass

    @abstractmethod
    async def copy_from(
        self,
        sandbox_id: str,
        src_path: str,
        dst_path: str,
    ) -> bool:
        """Copy a file or directory from sandbox to host.

        Args:
            sandbox_id: The sandbox to copy from.
            src_path: Source path inside the sandbox.
            dst_path: Destination path on the host.

        Returns:
            True if copy succeeded, False otherwise.

        Raises:
            SandboxNotFoundError: If the sandbox doesn't exist.
            FileNotFoundError: If source file doesn't exist in sandbox.
        """
        pass

    @abstractmethod
    async def get_info(self, sandbox_id: str) -> SandboxInfo | None:
        """Get information about a sandbox.

        Args:
            sandbox_id: The sandbox to query.

        Returns:
            SandboxInfo if found, None otherwise.
        """
        pass

    @abstractmethod
    async def stop(self, sandbox_id: str) -> bool:
        """Stop a running sandbox.

        Args:
            sandbox_id: The sandbox to stop.

        Returns:
            True if stopped successfully, False otherwise.
        """
        pass

    @abstractmethod
    async def destroy(self, sandbox_id: str) -> bool:
        """Destroy a sandbox and clean up resources.

        Args:
            sandbox_id: The sandbox to destroy.

        Returns:
            True if destroyed successfully, False otherwise.
        """
        pass

    @abstractmethod
    async def list_sandboxes(self) -> list[SandboxInfo]:
        """List all active sandboxes.

        Returns:
            List of SandboxInfo for all active sandboxes.
        """
        pass

    @abstractmethod
    async def cleanup_all(self) -> int:
        """Clean up all sandboxes managed by this executor.

        Returns:
            Number of sandboxes cleaned up.
        """
        pass

    # ==================== Convenience Methods ====================

    async def execute_script(
        self,
        sandbox_id: str,
        script: str,
        interpreter: str = "/bin/sh",
        timeout: int | None = None,
    ) -> ExecutionResult:
        """Execute a multi-line script within the sandbox.

        Args:
            sandbox_id: The sandbox to execute in.
            script: The script content to execute.
            interpreter: The interpreter to use (default: /bin/sh).
            timeout: Execution timeout in seconds.

        Returns:
            ExecutionResult from script execution.
        """
        # Escape the script content and execute via interpreter
        escaped_script = script.replace("'", "'\\''")
        command = f"{interpreter} -c '{escaped_script}'"
        return await self.execute(sandbox_id, command, timeout)

    async def is_running(self, sandbox_id: str) -> bool:
        """Check if a sandbox is currently running.

        Args:
            sandbox_id: The sandbox to check.

        Returns:
            True if running, False otherwise.
        """
        from .types import SandboxStatus

        info = await self.get_info(sandbox_id)
        return info is not None and info.status == SandboxStatus.RUNNING


class SandboxError(Exception):
    """Base exception for sandbox-related errors."""

    pass


class SandboxCreationError(SandboxError):
    """Raised when sandbox creation fails."""

    pass


class SandboxNotFoundError(SandboxError):
    """Raised when a sandbox cannot be found."""

    pass


class SandboxExecutionError(SandboxError):
    """Raised when command execution fails."""

    pass


class SandboxTimeoutError(SandboxError):
    """Raised when command execution times out."""

    pass
