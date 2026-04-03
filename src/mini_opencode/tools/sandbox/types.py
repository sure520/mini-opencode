"""Type definitions for the sandbox execution system.

This module defines the core data models for sandbox execution:
- SandboxConfig: Configuration for sandbox creation
- ExecutionResult: Result from command execution in sandbox
- SandboxStatus: Current status of a sandbox instance
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SandboxProvider(str, Enum):
    """Sandbox provider enumeration."""

    DOCKER = "docker"
    FIRECRACKER = "firecracker"  # Future support
    NONE = "none"  # Direct execution (no sandbox)


class SandboxStatus(str, Enum):
    """Sandbox instance status."""

    CREATING = "creating"
    RUNNING = "running"
    STOPPED = "stopped"
    DESTROYED = "destroyed"
    ERROR = "error"


class NetworkMode(str, Enum):
    """Network isolation mode."""

    DISABLED = "disabled"  # No network access
    HOST = "host"  # Full host network access (dangerous)
    BRIDGE = "bridge"  # Isolated bridge network
    ISOLATED = "isolated"  # Isolated with no external access


@dataclass
class ResourceLimits:
    """Resource limits for sandbox execution.

    Attributes:
        cpu_count: Number of CPUs available (e.g., 1.0 = 1 CPU).
        memory_mb: Memory limit in megabytes.
        disk_mb: Disk space limit in megabytes.
        pids_limit: Maximum number of processes.
    """

    cpu_count: float = 1.0
    memory_mb: int = 512
    disk_mb: int = 1024
    pids_limit: int = 100

    def to_docker_config(self) -> dict[str, Any]:
        """Convert to Docker container config."""
        return {
            "nano_cpus": int(self.cpu_count * 1e9),  # Docker uses nanoseconds
            "mem_limit": f"{self.memory_mb}m",
            "pids_limit": self.pids_limit,
        }


@dataclass
class SandboxConfig:
    """Configuration for sandbox creation.

    Attributes:
        provider: The sandbox provider to use.
        image: Docker image to use for the sandbox.
        working_dir: Working directory inside the sandbox.
        mount_paths: Paths to mount from host to sandbox.
        resource_limits: Resource constraints for the sandbox.
        network_mode: Network isolation mode.
        timeout_seconds: Default command execution timeout.
        environment: Environment variables to set.
        auto_remove: Whether to auto-remove container after stop.
    """

    provider: SandboxProvider = SandboxProvider.DOCKER
    image: str = "python:3.12-slim"
    working_dir: str = "/workspace"
    mount_paths: dict[str, str] = field(default_factory=dict)
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    network_mode: NetworkMode = NetworkMode.DISABLED
    timeout_seconds: int = 60
    environment: dict[str, str] = field(default_factory=dict)
    auto_remove: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SandboxConfig":
        """Create config from dictionary."""
        resource_data = data.get("resource_limits", {})
        resource_limits = ResourceLimits(
            cpu_count=resource_data.get("cpu", 1.0),
            memory_mb=resource_data.get("memory_mb", 512),
            disk_mb=resource_data.get("disk_mb", 1024),
            pids_limit=resource_data.get("pids_limit", 100),
        )

        return cls(
            provider=SandboxProvider(data.get("provider", "docker")),
            image=data.get("image", "python:3.12-slim"),
            working_dir=data.get("working_dir", "/workspace"),
            mount_paths=data.get("mount_paths", {}),
            resource_limits=resource_limits,
            network_mode=NetworkMode(data.get("network", "disabled")),
            timeout_seconds=data.get("timeout", 60),
            environment=data.get("environment", {}),
            auto_remove=data.get("auto_remove", True),
        )


@dataclass
class ExecutionResult:
    """Result from command execution in sandbox.

    Attributes:
        success: Whether the command executed successfully.
        exit_code: The command's exit code.
        stdout: Standard output from the command.
        stderr: Standard error from the command.
        duration_ms: Execution duration in milliseconds.
        timed_out: Whether the command timed out.
        error_message: Error message if execution failed.
    """

    success: bool
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    timed_out: bool = False
    error_message: str = ""

    @classmethod
    def success_result(
        cls,
        stdout: str = "",
        stderr: str = "",
        exit_code: int = 0,
        duration_ms: int = 0,
    ) -> "ExecutionResult":
        """Create a successful execution result."""
        return cls(
            success=True,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
        )

    @classmethod
    def failure_result(
        cls,
        error_message: str,
        exit_code: int = 1,
        stdout: str = "",
        stderr: str = "",
        timed_out: bool = False,
    ) -> "ExecutionResult":
        """Create a failed execution result."""
        return cls(
            success=False,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            timed_out=timed_out,
            error_message=error_message,
        )

    @property
    def output(self) -> str:
        """Get combined output (stdout + stderr)."""
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(f"[stderr] {self.stderr}")
        if self.error_message:
            parts.append(f"[error] {self.error_message}")
        return "\n".join(parts) if parts else ""


@dataclass
class SandboxInfo:
    """Information about a sandbox instance.

    Attributes:
        sandbox_id: Unique identifier for the sandbox.
        container_id: Docker container ID (if applicable).
        status: Current status of the sandbox.
        config: Configuration used to create the sandbox.
        created_at: When the sandbox was created.
        started_at: When the sandbox started running.
        stopped_at: When the sandbox was stopped.
    """

    sandbox_id: str
    container_id: str = ""
    status: SandboxStatus = SandboxStatus.CREATING
    config: SandboxConfig = field(default_factory=SandboxConfig)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    stopped_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "sandbox_id": self.sandbox_id,
            "container_id": self.container_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
        }


# Default sandbox configuration
DEFAULT_SANDBOX_CONFIG = SandboxConfig()
