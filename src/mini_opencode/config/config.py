import os
import threading
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# Global configuration cache
__config: dict[str, Any] | None = None
__lock = threading.Lock()

load_dotenv()


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """
    Load configuration from a YAML file.

    Args:
        config_path: Path to the configuration file. If None, it checks the
                     MINI_OPENCODE_CONFIG environment variable or defaults to 'config.yaml'.

    Returns:
        The loaded configuration as a dictionary.

    Raises:
        FileNotFoundError: If the configuration file cannot be found.
        yaml.YAMLError: If the configuration file is not valid YAML.
    """
    global __config

    if __config is not None:
        return __config

    with __lock:
        # Double-checked locking pattern
        if __config is not None:
            return __config

        if config_path is None:
            config_path = os.getenv("MINI_OPENCODE_CONFIG", "config.yaml")

        path = Path(config_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Configuration file not found at: {path.absolute()}. "
                "Please ensure config.yaml exists or set MINI_OPENCODE_CONFIG environment variable."
            )

        with path.open("r", encoding="utf-8") as f:
            try:
                data = yaml.safe_load(f)
                config_data = data if data is not None else {}
                __config = _expand_env_vars(config_data)
            except yaml.YAMLError as e:
                raise yaml.YAMLError(
                    f"Error parsing configuration file {path}: {e}"
                ) from e

    return __config


def _expand_env_vars(data: Any) -> Any:
    """
    Recursively expand environment variables in the configuration data.
    Environment variables are identified by a leading '$' (e.g., '$API_KEY').
    """
    if isinstance(data, dict):
        return {k: _expand_env_vars(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_expand_env_vars(item) for item in data]
    elif isinstance(data, str) and data.startswith("$"):
        # Remove the leading '$' and get the environment variable value
        env_var = data[1:]
        # If the environment variable is not set, return the original string
        return os.getenv(env_var, data)
    return data


def get_config_section(key: str | list[str]) -> Any:
    """
    Get a specific section or value from the configuration.

    Args:
        key: A string key or a list of keys for nested access.

    Returns:
        The configuration value or None if not found.
    """
    # Ensure config is loaded
    try:
        config = load_config()
    except FileNotFoundError:
        return None

    keys = [key] if isinstance(key, str) else key

    section = config
    for k in keys:
        if not isinstance(section, dict) or k not in section:
            return None
        section = section[k]

    return section


if __name__ == "__main__":
    print(get_config_section("models"))
