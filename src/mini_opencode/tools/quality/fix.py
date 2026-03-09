"""Quality fix tool for mini-OpenCode."""

import subprocess
from typing import Optional
from langchain.tools import ToolRuntime, tool

from mini_opencode.tools.reminders import generate_reminders


@tool("quality_fix")
def quality_fix(
    runtime: ToolRuntime,
    path: Optional[str] = ".",
    fix_ruff: bool = True,
) -> str:
    """Automatically fix code quality issues.

    Args:
        path: The path to fix (default: "." for current directory).
        fix_ruff: Whether to fix ruff issues (default: True).

    Returns:
        str: The fix results.
    """
    reminders = generate_reminders(runtime)
    results = []

    # Run ruff fix
    if fix_ruff:
        try:
            ruff_result = subprocess.run(
                ["ruff", "check", "--fix", path],
                capture_output=True,
                text=True,
                cwd="."
            )
            if ruff_result.returncode == 0:
                results.append("✅ Ruff fix completed successfully")
                if ruff_result.stdout:
                    results.append("Fixes applied:")
                    results.append(ruff_result.stdout)
            else:
                results.append("❌ Ruff fix failed:")
                results.append(ruff_result.stdout)
                if ruff_result.stderr:
                    results.append("Stderr:")
                    results.append(ruff_result.stderr)
        except Exception as e:
            results.append(f"❌ Error running ruff fix: {str(e)}")

    # Note: mypy doesn't have an automatic fix option
    results.append("⚠️  Mypy issues need to be fixed manually")

    if not results:
        return f"No fixes were applied.{reminders}"

    return f"```\n{'\n'.join(results)}\n```{reminders}"
