from pathlib import Path
from typing import Union


class Project:
    """
    Represents a target project directory.

    Attributes:
        _root_dir (Path): The root directory of the project.
    """

    _root_dir: Path

    def __init__(self, path: Union[str, Path]):
        """
        Initialize the Project with a root directory.

        Args:
            path: The path to the project root directory.
        """
        self.root_dir = path

    @property
    def root_dir(self) -> Path:
        """Path: The project root directory."""
        return self._root_dir

    @root_dir.setter
    def root_dir(self, path: Union[str, Path]):
        """
        Set the project root directory and validate its existence.

        Args:
            path: The path to set as the project root.

        Raises:
            FileNotFoundError: If the path does not exist.
            NotADirectoryError: If the path is not a directory.
        """
        path_obj = Path(path).resolve()
        if not path_obj.exists():
            raise FileNotFoundError(f"Project root directory {path_obj} does not exist")
        if not path_obj.is_dir():
            raise NotADirectoryError(
                f"Project root directory {path_obj} is not a directory"
            )
        self._root_dir = path_obj


# Default project instance initialized to current working directory
project = Project(Path.cwd())
