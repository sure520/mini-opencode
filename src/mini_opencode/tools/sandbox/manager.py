"""Sandbox manager for high-level sandbox operations.

This module provides a high-level interface for managing sandbox
execution, including automatic sandbox lifecycle management.
"""

import asyncio
from typing import Any

import structlog

from mini_opencode.config import get_config_section

from .docker_executor import DockerSandboxExecutor
from .executor import SandboxExecutor
from .types import (
    ExecutionResult,
    NetworkMode,
    ResourceLimits,
    SandboxConfig,
    SandboxProvider,
)

logger = structlog.get_logger()


class SandboxManager:
    """High-level manager for sandbox operations.

    This class provides a simplified interface for executing commands
    in sandboxes with automatic lifecycle management.
    """

    def __init__(
        self,
        config: SandboxConfig | None = None,
        project_root: str | None = None,
    ) -> None:
        """Initialize the sandbox manager.

        Args:
            config: Sandbox configuration. If None, loads from config.yaml.
            project_root: Project root directory to mount in sandbox.
        """
        self._config = config or self._load_config()
        self._project_root = project_root
        self._executor: SandboxExecutor | None = None
        self._current_sandbox_id: str | None = None
        self._enabled = self._config.provider != SandboxProvider.NONE

        logger.debug(
            "sandbox_manager.initialized",
            enabled=self._enabled,
            provider=self._config.provider.value,
        )

    def _load_config(self) -> SandboxConfig:
        """Load sandbox configuration from config.yaml."""
        sandbox_config = get_config_section(["sandbox"])

        if sandbox_config is None or not isinstance(sandbox_config, dict):
            # Return disabled config if not configured
            return SandboxConfig(provider=SandboxProvider.NONE)

        if not sandbox_config.get("enabled", False):
            return SandboxConfig(provider=SandboxProvider.NONE)

        # Parse resource limits
        resource_data = sandbox_config.get("resource_limits", {})
        resource_limits = ResourceLimits(
            cpu_count=float(resource_data.get("cpu", 1.0)),
            memory_mb=self._parse_memory(resource_data.get("memory", "512M")),
            disk_mb=self._parse_memory(resource_data.get("disk", "1G")),
            pids_limit=resource_data.get("pids_limit", 100),
        )

        # Parse network mode
        network_str = sandbox_config.get("network", "disabled")
        try:
            network_mode = NetworkMode(network_str)
        except ValueError:
            network_mode = NetworkMode.DISABLED

        return SandboxConfig(
            provider=SandboxProvider(sandbox_config.get("provider", "docker")),
            image=sandbox_config.get("image", "python:3.12-slim"),
            working_dir=sandbox_config.get("working_dir", "/workspace"),
            resource_limits=resource_limits,
            network_mode=network_mode,
            timeout_seconds=sandbox_config.get("timeout", 60),
            environment=sandbox_config.get("environment", {}),
        )

    def _parse_memory(self, value: str | int) -> int:
        """Parse memory value like '512M' or '1G' to megabytes."""
        if isinstance(value, int):
            return value

        value = str(value).upper().strip()
        if value.endswith("G"):
            return int(float(value[:-1]) * 1024)
        elif value.endswith("M"):
            return int(float(value[:-1]))
        elif value.endswith("K"):
            return int(float(value[:-1]) / 1024)
        else:
            return int(value)

    @property
    def is_enabled(self) -> bool:
        """Check if sandbox execution is enabled."""
        return self._enabled

    def _get_executor(self) -> SandboxExecutor:
        """Get or create the sandbox executor."""
        if self._executor is None:
            if self._config.provider == SandboxProvider.DOCKER:
                self._executor = DockerSandboxExecutor()
            else:
                raise ValueError(f"Unsupported provider: {self._config.provider}")
        return self._executor

    async def _ensure_sandbox(self) -> str:
        """Ensure a sandbox is running, creating one if needed.

        Returns:
            The sandbox ID.
        """
        executor = self._get_executor()

        # Check if current sandbox is still running
        if self._current_sandbox_id:
            if await executor.is_running(self._current_sandbox_id):
                return self._current_sandbox_id
            else:
                # Sandbox died, clean it up
                await executor.destroy(self._current_sandbox_id)
                self._current_sandbox_id = None

        # Create new sandbox
        config = self._config

        # Add project root mount if provided
        if self._project_root:
            config.mount_paths[self._project_root] = config.working_dir

        sandbox_info = await executor.create(config)
        self._current_sandbox_id = sandbox_info.sandbox_id

        logger.info(
            "sandbox_manager.sandbox_created",
            sandbox_id=self._current_sandbox_id,
        )

        return self._current_sandbox_id

    async def execute(
        self,
        command: str,
        timeout: int | None = None,
        working_dir: str | None = None,
    ) -> ExecutionResult:
        """Execute a command in the sandbox.

        Args:
            command: The command to execute.
            timeout: Execution timeout in seconds.
            working_dir: Working directory for the command.

        Returns:
            ExecutionResult with command output and status.
        """
        if not self.is_enabled:
            return ExecutionResult.failure_result(
                error_message="Sandbox execution is not enabled",
            )

        try:
            sandbox_id = await self._ensure_sandbox()
            executor = self._get_executor()
            return await executor.execute(
                sandbox_id,
                command,
                timeout=timeout,
                working_dir=working_dir,
            )
        except Exception as e:
            logger.error("sandbox_manager.execute_failed", error=str(e))
            return ExecutionResult.failure_result(
                error_message=f"Sandbox execution failed: {e}",
            )

    async def execute_safely(
        self,
        command: str,
        timeout: int | None = None,
    ) -> ExecutionResult:
        """Execute a command safely, falling back to direct execution if sandbox unavailable.

        This method tries to use the sandbox, but falls back to a
        restricted direct execution if the sandbox is not available.

        Args:
            command: The command to execute.
            timeout: Execution timeout in seconds.

        Returns:
            ExecutionResult with command output and status.
        """
        if self.is_enabled:
            try:
                return await self.execute(command, timeout)
            except Exception as e:
                logger.warning(
                    "sandbox_manager.fallback_to_direct",
                    error=str(e),
                )

        # Fallback: direct execution (with safety checks)
        return await self._execute_direct(command, timeout or 60)

    async def _execute_direct(
        self,
        command: str,
        timeout: int,
    ) -> ExecutionResult:
        """Execute command directly (without sandbox).

        This is a fallback when sandbox is unavailable. It applies
        basic safety checks but is less secure than sandbox execution.

        Args:
            command: The command to execute.
            timeout: Execution timeout in seconds.

        Returns:
            ExecutionResult with command output and status.
        """
        import subprocess
        import time

        start_time = time.time()

        try:
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: subprocess.run(
                        command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                    ),
                ),
                timeout=timeout + 5,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            if result.returncode == 0:
                return ExecutionResult.success_result(
                    stdout=result.stdout,
                    stderr=result.stderr,
                    exit_code=result.returncode,
                    duration_ms=duration_ms,
                )
            else:
                return ExecutionResult.failure_result(
                    error_message=f"Command exited with code {result.returncode}",
                    exit_code=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                )

        except asyncio.TimeoutError:
            return ExecutionResult.failure_result(
                error_message=f"Command timed out after {timeout} seconds",
                timed_out=True,
            )
        except Exception as e:
            return ExecutionResult.failure_result(
                error_message=f"Command execution failed: {e}",
            )

    async def cleanup(self) -> None:
        """Clean up current sandbox."""
        if self._current_sandbox_id and self._executor:
            await self._executor.destroy(self._current_sandbox_id)
            self._current_sandbox_id = None
            logger.info("sandbox_manager.cleaned_up")

    async def cleanup_all(self) -> int:
        """Clean up all sandboxes.

        Returns:
            Number of sandboxes cleaned up.
        """
        if self._executor:
            count = await self._executor.cleanup_all()
            self._current_sandbox_id = None
            return count
        return 0

    def get_stats(self) -> dict[str, Any]:
        """Get sandbox manager statistics."""
        return {
            "enabled": self.is_enabled,
            "provider": self._config.provider.value,
            "current_sandbox": self._current_sandbox_id,
            "image": self._config.image,
            "timeout": self._config.timeout_seconds,
            "network_mode": self._config.network_mode.value,
        }


# Singleton instance
_manager: SandboxManager | None = None


def get_sandbox_manager(project_root: str | None = None) -> SandboxManager:
    """Get the default sandbox manager.

    Args:
        project_root: Project root directory to mount.

    Returns:
        The singleton SandboxManager instance.
    """
    global _manager
    if _manager is None:
        _manager = SandboxManager(project_root=project_root)
    return _manager
