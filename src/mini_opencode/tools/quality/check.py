"""Quality check tool for mini-OpenCode."""

import subprocess
from typing import Optional
from langchain.tools import ToolRuntime, tool

from mini_opencode.tools.reminders import generate_reminders


@tool("quality_check")
def quality_check(
    runtime: ToolRuntime,
    path: Optional[str] = ".",
    include_ruff: bool = True,
    include_mypy: bool = True,
) -> str:
    """Run code quality checks on the specified path.

    Args:
        path: The path to check (default: "." for current directory).
        include_ruff: Whether to include ruff checks (default: True).
        include_mypy: Whether to include mypy checks (default: True).

    Returns:
        str: The quality check results.
    """
    reminders = generate_reminders(runtime)
    results = []

    # Run ruff check
    if include_ruff:
        try:
            ruff_result = subprocess.run(
                ["ruff", "check", path],
                capture_output=True,
                text=True,
                cwd="."
            )
            if ruff_result.returncode == 0:
                results.append("✅ Ruff check passed")
            else:
                results.append("❌ Ruff check failed:")
                results.append(ruff_result.stdout)
                if ruff_result.stderr:
                    results.append("Stderr:")
                    results.append(ruff_result.stderr)
        except Exception as e:
            results.append(f"❌ Error running ruff: {str(e)}")

    # Run mypy check
    if include_mypy:
        try:
            mypy_result = subprocess.run(
                ["mypy", path],
                capture_output=True,
                text=True,
                cwd="."
            )
            if mypy_result.returncode == 0:
                results.append("✅ Mypy check passed")
            else:
                results.append("❌ Mypy check failed:")
                results.append(mypy_result.stdout)
                if mypy_result.stderr:
                    results.append("Stderr:")
                    results.append(mypy_result.stderr)
        except Exception as e:
            results.append(f"❌ Error running mypy: {str(e)}")

    if not results:
        return f"No quality checks were run.{reminders}"

    return f"```\n{'\n'.join(results)}\n```{reminders}"
