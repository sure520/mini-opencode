import subprocess

from textual.theme import Theme

DARK_THEME = Theme(
    name="dark",
    dark=True,
    # Primary colors
    primary="#58a6ff",
    secondary="#8b949e",
    accent="#f78166",
    foreground="#c9d1d9",
    # Background colors
    background="#1d2227",
    surface="#161b22",
    panel="#1f2428",
    boost="#24292e",
    # Informational colors
    success="#3fb950",
    warning="#d29922",
    error="#f85149",
)

LIGHT_THEME = Theme(
    name="light",
    dark=False,
    # Primary colors
    primary="#0969da",
    secondary="#57606a",
    accent="#cf222e",
    foreground="#24292f",
    # Background colors
    background="#ffffff",
    surface="#f6f8fa",
    panel="#f6f8fa",
    boost="#ebf0f4",
    # Informational colors
    success="#1a7f37",
    warning="#9a6700",
    error="#cf222e",
)


def is_dark_mode() -> bool:
    """Check if the macOS system is in dark mode."""
    try:
        result = subprocess.run(
            ["defaults", "read", "-g", "AppleInterfaceStyle"],
            capture_output=True,
            text=True,
            check=False,
        )
        return "Dark" in result.stdout
    except Exception:
        # Default to dark mode if check fails or not on macOS
        return True
