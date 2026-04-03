"""Docker-based sandbox executor implementation.

This module provides a Docker-based implementation of the SandboxExecutor
interface for isolated command execution.
"""

import asyncio
import io
import tarfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from .executor import (
    SandboxCreationError,
    SandboxExecutionError,
    SandboxExecutor,
    SandboxNotFoundError,
    SandboxTimeoutError,
)
from .types import (
    ExecutionResult,
    NetworkMode,
    SandboxConfig,
    SandboxInfo,
    SandboxStatus,
)

logger = structlog.get_logger()


class DockerSandboxExecutor(SandboxExecutor):
    """Docker-based sandbox executor.

    This implementation uses Docker containers to provide isolated
    execution environments with configurable resource limits and
    network isolation.
    """

    def __init__(self) -> None:
        """Initialize the Docker sandbox executor."""
        self._client: Any = None
        self._sandboxes: dict[str, SandboxInfo] = {}
        self._containers: dict[str, Any] = {}
        self._label_prefix = "mini-opencode-sandbox"

    def _get_client(self) -> Any:
        """Get or create Docker client."""
        if self._client is None:
            try:
                import docker

                self._client = docker.from_env()
                # Test connection
                self._client.ping()
                logger.debug("docker_sandbox.client_connected")
            except Exception as e:
                logger.error("docker_sandbox.client_failed", error=str(e))
                raise SandboxCreationError(f"Failed to connect to Docker: {e}") from e
        return self._client

    def _get_network_mode(self, mode: NetworkMode) -> str | None:
        """Convert NetworkMode to Docker network mode string."""
        if mode == NetworkMode.HOST:
            return "host"
        elif mode == NetworkMode.BRIDGE:
            return "bridge"
        elif mode == NetworkMode.DISABLED or mode == NetworkMode.ISOLATED:
            return "none"
        return "none"

    async def create(self, config: SandboxConfig) -> SandboxInfo:
        """Create a new Docker sandbox container.

        Args:
            config: Configuration for the sandbox.

        Returns:
            SandboxInfo containing the sandbox ID and container details.

        Raises:
            SandboxCreationError: If container creation fails.
        """
        sandbox_id = str(uuid.uuid4())[:12]
        client = self._get_client()

        try:
            # Prepare container configuration
            container_config: dict[str, Any] = {
                "image": config.image,
                "name": f"{self._label_prefix}-{sandbox_id}",
                "labels": {
                    f"{self._label_prefix}.id": sandbox_id,
                    f"{self._label_prefix}.managed": "true",
                },
                "working_dir": config.working_dir,
                "stdin_open": True,
                "tty": False,
                "detach": True,
                "auto_remove": False,  # We manage removal ourselves
                "network_mode": self._get_network_mode(config.network_mode),
            }

            # Apply resource limits
            limits = config.resource_limits.to_docker_config()
            container_config.update(limits)

            # Set up volume mounts
            if config.mount_paths:
                volumes = {}
                for host_path, container_path in config.mount_paths.items():
                    # Mount as read-only for security
                    volumes[host_path] = {"bind": container_path, "mode": "ro"}
                container_config["volumes"] = volumes

            # Set environment variables
            if config.environment:
                container_config["environment"] = config.environment

            # Pull image if not exists
            loop = asyncio.get_event_loop()
            try:
                await loop.run_in_executor(None, lambda: client.images.get(config.image))
            except Exception:
                logger.info("docker_sandbox.pulling_image", image=config.image)
                await loop.run_in_executor(None, lambda: client.images.pull(config.image))

            # Create container
            container = await loop.run_in_executor(
                None,
                lambda: client.containers.create(**container_config),
            )

            # Start container
            await loop.run_in_executor(None, container.start)

            # Create sandbox info
            sandbox_info = SandboxInfo(
                sandbox_id=sandbox_id,
                container_id=container.id,
                status=SandboxStatus.RUNNING,
                config=config,
                created_at=datetime.now(),
                started_at=datetime.now(),
            )

            self._sandboxes[sandbox_id] = sandbox_info
            self._containers[sandbox_id] = container

            logger.info(
                "docker_sandbox.created",
                sandbox_id=sandbox_id,
                container_id=container.short_id,
                image=config.image,
            )

            return sandbox_info

        except Exception as e:
            logger.error("docker_sandbox.create_failed", error=str(e))
            raise SandboxCreationError(f"Failed to create sandbox: {e}") from e

    async def execute(
        self,
        sandbox_id: str,
        command: str,
        timeout: int | None = None,
        working_dir: str | None = None,
    ) -> ExecutionResult:
        """Execute a command in the Docker sandbox.

        Args:
            sandbox_id: The sandbox to execute in.
            command: The command to execute.
            timeout: Execution timeout in seconds.
            working_dir: Working directory for the command.

        Returns:
            ExecutionResult with command output and status.
        """
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(f"Sandbox {sandbox_id} not found")

        sandbox_info = self._sandboxes[sandbox_id]
        container = self._containers.get(sandbox_id)

        if container is None:
            raise SandboxNotFoundError(f"Container for sandbox {sandbox_id} not found")

        timeout = timeout or sandbox_info.config.timeout_seconds
        start_time = time.time()

        try:
            loop = asyncio.get_event_loop()

            # Prepare exec configuration
            exec_config: dict[str, Any] = {
                "cmd": ["/bin/sh", "-c", command],
                "stdout": True,
                "stderr": True,
                "stream": False,
            }

            if working_dir:
                exec_config["workdir"] = working_dir

            # Execute command with timeout
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: container.exec_run(**exec_config),
                    ),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                duration_ms = int((time.time() - start_time) * 1000)
                logger.warning(
                    "docker_sandbox.command_timeout",
                    sandbox_id=sandbox_id,
                    command=command[:100],
                    timeout=timeout,
                )
                return ExecutionResult.failure_result(
                    error_message=f"Command timed out after {timeout} seconds",
                    timed_out=True,
                )

            duration_ms = int((time.time() - start_time) * 1000)
            exit_code = result.exit_code
            output = result.output.decode("utf-8", errors="replace") if result.output else ""

            # Split stdout and stderr if possible
            # Docker exec_run combines them, so we can't easily separate
            if exit_code == 0:
                return ExecutionResult.success_result(
                    stdout=output,
                    exit_code=exit_code,
                    duration_ms=duration_ms,
                )
            else:
                return ExecutionResult.failure_result(
                    error_message=f"Command exited with code {exit_code}",
                    exit_code=exit_code,
                    stderr=output,
                )

        except asyncio.TimeoutError:
            raise SandboxTimeoutError(f"Command timed out after {timeout} seconds")
        except Exception as e:
            logger.error(
                "docker_sandbox.execute_failed",
                sandbox_id=sandbox_id,
                error=str(e),
            )
            raise SandboxExecutionError(f"Command execution failed: {e}") from e

    async def copy_to(
        self,
        sandbox_id: str,
        src_path: str,
        dst_path: str,
    ) -> bool:
        """Copy a file from host to sandbox.

        Args:
            sandbox_id: The sandbox to copy to.
            src_path: Source path on the host.
            dst_path: Destination path in the sandbox.

        Returns:
            True if copy succeeded.
        """
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(f"Sandbox {sandbox_id} not found")

        container = self._containers.get(sandbox_id)
        if container is None:
            raise SandboxNotFoundError(f"Container for sandbox {sandbox_id} not found")

        src = Path(src_path)
        if not src.exists():
            raise FileNotFoundError(f"Source file not found: {src_path}")

        try:
            loop = asyncio.get_event_loop()

            # Create tar archive of the file
            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode="w") as tar:
                tar.add(src_path, arcname=Path(src_path).name)
            tar_stream.seek(0)

            # Copy to container
            dst_dir = str(Path(dst_path).parent)
            await loop.run_in_executor(
                None,
                lambda: container.put_archive(dst_dir, tar_stream.read()),
            )

            logger.debug(
                "docker_sandbox.file_copied_to",
                sandbox_id=sandbox_id,
                src=src_path,
                dst=dst_path,
            )
            return True

        except Exception as e:
            logger.error("docker_sandbox.copy_to_failed", error=str(e))
            return False

    async def copy_from(
        self,
        sandbox_id: str,
        src_path: str,
        dst_path: str,
    ) -> bool:
        """Copy a file from sandbox to host.

        Args:
            sandbox_id: The sandbox to copy from.
            src_path: Source path in the sandbox.
            dst_path: Destination path on the host.

        Returns:
            True if copy succeeded.
        """
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(f"Sandbox {sandbox_id} not found")

        container = self._containers.get(sandbox_id)
        if container is None:
            raise SandboxNotFoundError(f"Container for sandbox {sandbox_id} not found")

        try:
            loop = asyncio.get_event_loop()

            # Get archive from container
            bits, _ = await loop.run_in_executor(
                None,
                lambda: container.get_archive(src_path),
            )

            # Extract to host
            tar_stream = io.BytesIO()
            for chunk in bits:
                tar_stream.write(chunk)
            tar_stream.seek(0)

            dst = Path(dst_path)
            dst.parent.mkdir(parents=True, exist_ok=True)

            with tarfile.open(fileobj=tar_stream, mode="r") as tar:
                # Extract single file
                members = tar.getmembers()
                if members:
                    member = members[0]
                    member.name = dst.name
                    tar.extract(member, dst.parent)

            logger.debug(
                "docker_sandbox.file_copied_from",
                sandbox_id=sandbox_id,
                src=src_path,
                dst=dst_path,
            )
            return True

        except Exception as e:
            logger.error("docker_sandbox.copy_from_failed", error=str(e))
            return False

    async def get_info(self, sandbox_id: str) -> SandboxInfo | None:
        """Get information about a sandbox.

        Args:
            sandbox_id: The sandbox to query.

        Returns:
            SandboxInfo if found, None otherwise.
        """
        info = self._sandboxes.get(sandbox_id)
        if info is None:
            return None

        # Update status from container
        container = self._containers.get(sandbox_id)
        if container:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, container.reload)
                status = container.status

                if status == "running":
                    info.status = SandboxStatus.RUNNING
                elif status == "exited":
                    info.status = SandboxStatus.STOPPED
                elif status == "created":
                    info.status = SandboxStatus.CREATING
                else:
                    info.status = SandboxStatus.ERROR
            except Exception:
                info.status = SandboxStatus.ERROR

        return info

    async def stop(self, sandbox_id: str) -> bool:
        """Stop a running sandbox.

        Args:
            sandbox_id: The sandbox to stop.

        Returns:
            True if stopped successfully.
        """
        if sandbox_id not in self._sandboxes:
            return False

        container = self._containers.get(sandbox_id)
        if container is None:
            return False

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: container.stop(timeout=10))

            info = self._sandboxes[sandbox_id]
            info.status = SandboxStatus.STOPPED
            info.stopped_at = datetime.now()

            logger.info("docker_sandbox.stopped", sandbox_id=sandbox_id)
            return True

        except Exception as e:
            logger.error("docker_sandbox.stop_failed", error=str(e))
            return False

    async def destroy(self, sandbox_id: str) -> bool:
        """Destroy a sandbox and clean up resources.

        Args:
            sandbox_id: The sandbox to destroy.

        Returns:
            True if destroyed successfully.
        """
        if sandbox_id not in self._sandboxes:
            return False

        container = self._containers.get(sandbox_id)
        if container:
            try:
                loop = asyncio.get_event_loop()
                # Force remove even if running
                await loop.run_in_executor(
                    None,
                    lambda: container.remove(force=True),
                )
            except Exception as e:
                logger.warning("docker_sandbox.remove_failed", error=str(e))

        # Clean up tracking
        info = self._sandboxes.pop(sandbox_id, None)
        self._containers.pop(sandbox_id, None)

        if info:
            info.status = SandboxStatus.DESTROYED
            info.stopped_at = datetime.now()

        logger.info("docker_sandbox.destroyed", sandbox_id=sandbox_id)
        return True

    async def list_sandboxes(self) -> list[SandboxInfo]:
        """List all active sandboxes.

        Returns:
            List of SandboxInfo for all active sandboxes.
        """
        result = []
        for sandbox_id in list(self._sandboxes.keys()):
            info = await self.get_info(sandbox_id)
            if info:
                result.append(info)
        return result

    async def cleanup_all(self) -> int:
        """Clean up all sandboxes managed by this executor.

        Returns:
            Number of sandboxes cleaned up.
        """
        sandbox_ids = list(self._sandboxes.keys())
        cleaned = 0

        for sandbox_id in sandbox_ids:
            if await self.destroy(sandbox_id):
                cleaned += 1

        # Also clean up any orphaned containers
        try:
            client = self._get_client()
            loop = asyncio.get_event_loop()
            containers = await loop.run_in_executor(
                None,
                lambda: client.containers.list(
                    all=True,
                    filters={"label": f"{self._label_prefix}.managed=true"},
                ),
            )
            for container in containers:
                try:
                    await loop.run_in_executor(
                        None,
                        lambda c=container: c.remove(force=True),
                    )
                    cleaned += 1
                    logger.info(
                        "docker_sandbox.orphan_cleaned",
                        container_id=container.short_id,
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.warning("docker_sandbox.cleanup_orphans_failed", error=str(e))

        logger.info("docker_sandbox.cleanup_complete", count=cleaned)
        return cleaned


# Singleton instance for global use
_default_executor: DockerSandboxExecutor | None = None


def get_docker_executor() -> DockerSandboxExecutor:
    """Get the default Docker sandbox executor.

    Returns:
        The singleton DockerSandboxExecutor instance.
    """
    global _default_executor
    if _default_executor is None:
        _default_executor = DockerSandboxExecutor()
    return _default_executor
