from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

# Initialize Jinja2 environment lazily or at module level for performance
TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))


def apply_prompt_template(template_name: str, **kwargs: Any) -> str:
    """
    Apply a prompt template with the given keyword arguments.

    Args:
        template_name: The name of the template file (without .md extension) in the templates directory.
        **kwargs: The variables to be rendered in the template.

    Returns:
        The rendered prompt string.
    """
    template = _env.get_template(f"{template_name}.md")
    return template.render(**kwargs)
