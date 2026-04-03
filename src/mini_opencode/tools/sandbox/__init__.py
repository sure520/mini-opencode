"""Sandbox execution system for isolated command execution.

This module provides a sandbox system for safely executing commands
in isolated environments using Docker containers.

Example usage:
    from mini_opencode.tools.sandbox import (
        DockerSandboxExecutor,
        SandboxConfig,
        SandboxManager,
    )

    # Create executor and sandbox
    executor = DockerSandboxExecutor()
    config = SandboxConfig(image="python:3.12-slim")
    sandbox = await executor.create(config)

    # Execute command
    result = await executor.execute(sandbox.sandbox_id, "python --version")
    print(result.stdout)

    # Cleanup
    await executor.destroy(sandbox.sandbox_id)

Or use the high-level SandboxManager:
    manager = SandboxManager()
    result = await manager.execute_safely("python --version")
    print(result.output)
"""

from .docker_executor import DockerSandboxExecutor, get_docker_executor
from .executor import (
    SandboxCreationError,
    SandboxError,
    SandboxExecutionError,
    SandboxExecutor,
    SandboxNotFoundError,
    SandboxTimeoutError,
)
from .manager import SandboxManager, get_sandbox_manager
from .types import (
    DEFAULT_SANDBOX_CONFIG,
    ExecutionResult,
    NetworkMode,
    ResourceLimits,
    SandboxConfig,
    SandboxInfo,
    SandboxProvider,
    SandboxStatus,
)

__all__ = [
    # Types
    "SandboxProvider",
    "SandboxStatus",
    "NetworkMode",
    "ResourceLimits",
    "SandboxConfig",
    "ExecutionResult",
    "SandboxInfo",
    "DEFAULT_SANDBOX_CONFIG",
    # Executor interface
    "SandboxExecutor",
    # Docker implementation
    "DockerSandboxExecutor",
    "get_docker_executor",
    # Manager
    "SandboxManager",
    "get_sandbox_manager",
    # Exceptions
    "SandboxError",
    "SandboxCreationError",
    "SandboxNotFoundError",
    "SandboxExecutionError",
    "SandboxTimeoutError",
]
