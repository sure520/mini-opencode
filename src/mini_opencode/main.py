"""
Main entry point for the mini-OpenCode application.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

from .project import project

# Load environment variables from .env file if it exists
load_dotenv()


def main() -> None:
    """
    Main execution function for mini-OpenCode.

    Parses command line arguments to set the project root directory.
    """
    if len(sys.argv) > 1:
        new_root = Path(sys.argv[1])
        try:
            project.root_dir = new_root
            print(f"Project root set to: {project.root_dir}")
        except (FileNotFoundError, NotADirectoryError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
