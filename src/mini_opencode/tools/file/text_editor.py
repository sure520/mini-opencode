from pathlib import Path
from typing import Literal

from mini_opencode.cache.file_cache import file_cache
from mini_opencode.logging_config import get_logger

logger = get_logger(__name__)

TextEditorCommand = Literal[
    "read",
    "write",
    "edit",
]


class TextEditor:
    """A standalone text editor tool for AI agents to interact with files.

    This tool allows reading, writing, and editing files with proper error handling
    and suggestions to help AI agents learn from mistakes.
    """

    def validate_path(self, path: Path):
        """Validate the path for security and correctness.

        Args:
            path: The path to the file or directory.

        Raises:
            ValueError: If path is not absolute, contains directory traversal, or is outside allowed directories.
        """
        # Check that the path is absolute
        if not path.is_absolute():
            suggested_path = Path.cwd().resolve() / path
            raise ValueError(
                f"The path {path} is not an absolute path, it should start with `/`. Do you mean {suggested_path}?"
            )

        # Prevent directory traversal attacks
        try:
            resolved_path = path.resolve()
        except Exception as e:
            raise ValueError(f"Invalid path: {path}. Error: {e}")

        # Check for directory traversal
        path_str = str(path)
        if '..' in path_str or resolved_path != path:
            raise ValueError(
                f"Path contains directory traversal attempts: {path}"
            )

        # Path whitelist - only allow paths within the current working directory
        # This prevents access to system files and sensitive directories
        cwd = Path.cwd().resolve()
        if not resolved_path.is_relative_to(cwd):
            raise ValueError(
                f"Path {path} is outside the allowed directory: {cwd}"
            )

    def read(self, path: Path, read_range: list[int] | None = None) -> str:
        """Read the content of a file.

        Args:
            path: The absolute path to the file.
            read_range: Optional list of two integers [start, end] for line range.
                Line numbers are 1-indexed. Use -1 for end line to read to EOF.

        Returns:
            str: The file content with line numbers.

        Raises:
            ValueError: If file doesn't exist, is not a file, or read_range is invalid.
        """
        if not path.exists():
            raise ValueError(f"File does not exist: {path}")

        if not path.is_file():
            raise ValueError(f"Path is not a file: {path}")

        file_content = self.read_file(path)
        if not file_content:
            return ""

        init_line = 1
        if read_range:
            if len(read_range) != 2 or not all(isinstance(i, int) for i in read_range):
                raise ValueError(
                    "Invalid `read_range`. It should be a list of two integers."
                )

            file_lines = file_content.splitlines()
            n_lines_file = len(file_lines)

            # If file is not empty but splitlines is empty (shouldn't happen with check above)
            if n_lines_file == 0:
                return ""

            init_line, final_line = read_range

            # Validate the start line
            if init_line < 1 or init_line > n_lines_file:
                raise ValueError(
                    f"Invalid `read_range`: {read_range}. The start line `{init_line}` should be within the range of lines in the file: [1, {n_lines_file}]"
                )

            # Validate the end line
            if final_line != -1 and (
                final_line < init_line or final_line > n_lines_file
            ):
                if final_line > n_lines_file:
                    final_line = n_lines_file
                else:
                    raise ValueError(
                        f"Invalid `read_range`: {read_range}. The end line `{final_line}` should be -1 or "
                        f"within the range of lines in the file: [{init_line}, {n_lines_file}]"
                    )

            # Slice the file content based on the read range
            if final_line == -1:
                file_content = "\n".join(file_lines[init_line - 1 :])
            else:
                file_content = "\n".join(file_lines[init_line - 1 : final_line])

        return self._content_with_line_numbers(file_content, init_line=init_line)

    def edit(self, path: Path, old_str: str, new_str: str | None):
        """Replace the occurrence of old_str with new_str in the file.

        Args:
            path: The path to the file.
            old_str: The string to be replaced. The edit will FAIL if `old_str` is not unique in the file. Provide a larger string with more surrounding context to make it unique.
            new_str: The replacement string. If None, old_str will be removed.

        Returns:
            int: The count of replacements (should always be 1).

        Raises:
            ValueError: If file doesn't exist, is not a file, old_str not found, or old_str is not unique.
        """
        if not path.exists():
            raise ValueError(f"File does not exist: {path}")

        if not path.is_file():
            raise ValueError(f"Path is not a file: {path}")

        # Read the file content
        file_content = self.read_file(path)

        # Check if old_str exists and is unique
        occurrences = file_content.count(old_str)
        if occurrences == 0:
            raise ValueError(f"String not found in file: {path}")
        if occurrences > 1:
            raise ValueError(
                f"String found {occurrences} times in {path}. "
                "Please provide a more specific `old_str` with more surrounding context to make it unique."
            )

        # Perform the replacement
        if new_str is None:
            new_str = ""

        new_content = file_content.replace(old_str, new_str)

        # Write the modified content back to the file
        self.write_file(path, new_content)

        return occurrences

    def read_file(self, path: Path, chunk_size: int = 8192) -> str:
        """Read the raw content of a file with streaming support for large files.

        Args:
            path: The path to the file to read.
            chunk_size: The size of each chunk to read (default: 8192 bytes).

        Returns:
            str: The raw file content.

        Raises:
            ValueError: If the file cannot be read.
        """
        logger.info("Reading file", path=str(path))
        
        # 尝试从缓存获取
        cached_content = file_cache.get(str(path))
        if cached_content:
            logger.debug("Cache hit for file", path=str(path))
            return cached_content
        
        try:
            # 检查文件大小
            file_size = path.stat().st_size
            logger.debug("File size", path=str(path), size=file_size)
            
            # 对于小文件，直接读取
            if file_size < 1024 * 1024:  # 小于1MB
                logger.debug("Reading small file directly", path=str(path))
                content = path.read_text(encoding="utf-8")
            else:
                # 对于大文件，使用流式读取
                logger.debug("Reading large file with streaming", path=str(path))
                content = []
                with open(path, 'r', encoding="utf-8") as f:
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        content.append(chunk)
                content = ''.join(content)
            
            # 更新缓存（仅缓存小文件，避免内存占用过大）
            if file_size < 1024 * 1024:  # 小于1MB
                logger.debug("Caching file content", path=str(path))
                file_cache.set(str(path), content)
            
            logger.info("File read successfully", path=str(path), size=file_size)
            return content
        except Exception as e:
            logger.error("Error reading file", path=str(path), error=str(e))
            raise ValueError(f"Error reading {path}: {e}")

    def write_file(self, path: Path, content: str) -> None:
        """Write content to a file, creating parent directories if necessary.

        Args:
            path: The path to the file to write.
            content: The content to write.

        Raises:
            ValueError: If the file cannot be written.
        """
        logger.info("Writing file", path=str(path), content_length=len(content))
        
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            logger.debug("Created parent directories", path=str(path.parent))
            
            path.write_text(content, encoding="utf-8")
            logger.debug("Written content to file", path=str(path))
            
            # 清除缓存，确保下次读取时获取最新内容
            file_cache.clear(str(path))
            logger.debug("Cleared file cache", path=str(path))
            
            logger.info("File written successfully", path=str(path))
        except Exception as e:
            logger.error("Error writing file", path=str(path), error=str(e))
            raise ValueError(f"Error writing to {path}: {e}")

    def _content_with_line_numbers(
        self,
        file_content: str,
        init_line: int = 1,
    ) -> str:
        """Add line numbers to the content.

        Args:
            file_content: The content to add line numbers to.
            init_line: The starting line number.

        Returns:
            str: The content with line numbers.
        """
        if not file_content:
            return ""

        lines = file_content.splitlines()
        # Use a minimum width of 3, but expand if needed for large line numbers
        max_line = init_line + len(lines) - 1
        width = max(3, len(str(max_line)))

        formatted_lines = [
            f"{i + init_line:>{width}} {line}" for i, line in enumerate(lines)
        ]
        return "\n".join(formatted_lines)
