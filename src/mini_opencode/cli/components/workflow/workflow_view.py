"""Workflow progress view component.

Displays the current state of the multi-agent DAG workflow,
including phase, subtask status, and iteration information.
"""

from typing import Any

from textual.widgets import Static


class WorkflowView(Static):
    """Workflow progress view component.

    Displays subtask status, current phase, and iteration count
    for the Plan-Code-Test-Fix workflow.
    """

    DEFAULT_CSS = """
    WorkflowView {
        color: $text-muted;
        padding: 1 2;
    }
    """

    def on_mount(self) -> None:
        """Display initial empty state."""
        self.update("(No active workflow)")

    def update_status(
        self,
        phase: str,
        subtasks: list[dict[str, Any]],
        iteration: int = 0,
        max_iterations: int = 3,
    ) -> None:
        """Update the workflow status display.

        Args:
            phase: Current workflow phase (e.g. "executing", "completed").
            subtasks: List of subtask dicts with keys: task_id, task_type,
                      description, status.
            iteration: Current fix iteration number.
            max_iterations: Maximum fix iterations allowed.
        """
        lines: list[str] = []

        # Phase header
        phase_display = phase.upper() if phase else "UNKNOWN"
        iter_info = f"  (iteration {iteration}/{max_iterations})" if iteration > 0 else ""
        lines.append(f"Workflow: {phase_display}{iter_info}")
        lines.append("\u2500" * 36)

        if not subtasks:
            lines.append("  (no subtasks)")
        else:
            for task in subtasks:
                status = task.get("status", "pending")
                task_type = task.get("task_type", "unknown")
                description = task.get("description", "")
                task_id = task.get("task_id", "")

                icon = self._status_icon(status)
                # Truncate description to fit
                desc = description[:40] + "..." if len(description) > 40 else description
                lines.append(f"  {icon} {task_id} ({task_type}): {desc}")

        self.update("\n".join(lines))

    def clear_workflow(self) -> None:
        """Reset to initial empty state."""
        self.update("(No active workflow)")

    @staticmethod
    def _status_icon(status: str) -> str:
        """Get status icon for a subtask.

        Args:
            status: Task status string.

        Returns:
            Status icon character.
        """
        icons = {
            "completed": "\\[x]",
            "running": "\\[*]",
            "failed": "\\[!]",
            "pending": "\\[ ]",
            "cancelled": "\\[-]",
        }
        return icons.get(status, "\\[?]")
