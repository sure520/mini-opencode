import threading
import re

from langchain.tools import ToolRuntime, tool

from mini_opencode.project import project
from mini_opencode.tools.reminders import generate_reminders

from .bash_terminal import BashTerminal

# Use a thread lock and global variable for the terminal instance
# In a multi-user environment, this should ideally be stored in a session-specific context
terminal_lock = threading.Lock()
keep_alive_terminal: BashTerminal | None = None

# Dangerous command patterns that should be blocked
DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+/",           # 删除根目录
    r"mkfs\.\w+",              # 格式化文件系统
    r"dd\s+if=.*of=/dev",      # 直接写入设备
    r">\s*/dev/sda",           # 覆盖硬盘
    r":\(\)\{\s*:\|:&\s*\};:", # Fork 炸弹
    r"rm\s+-rf\s+\.",          # 删除当前目录
    r"chmod\s+777\s+/",        # 给根目录设置危险权限
    r"shutdown\s*-h\s+now",     # 立即关机
    r"reboot",                  # 重启系统
    r"poweroff",                # 关机
]

# Allowed commands (white list)
ALLOWED_COMMANDS = [
    "ls", "cd", "mkdir", "rmdir", "touch", "cp", "mv", "cat",
    "git", "python", "pip", "uv", "make", "npm", "yarn", "pnpm",
    "echo", "grep", "find", "head", "tail", "wc", "sort", "uniq",
    "tar", "zip", "unzip", "curl", "wget", "ping", "ps", "top",
]


def is_dangerous_command(command: str) -> bool:
    """Check if a command is dangerous."""
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False


def is_allowed_command(command: str) -> bool:
    """Check if a command is allowed."""
    # Extract the main command
    main_command = command.split()[0] if command.strip() else ""
    return main_command in ALLOWED_COMMANDS


@tool("bash")
def bash_tool(
    runtime: ToolRuntime,
    command: str,
    reset_cwd: bool | None = False,
    timeout: int | None = 60,
):
    """Execute a standard bash command in a keep-alive shell, and return the output if successful or error message if failed.

    Use this tool to perform:
    - Create directories
    - Install dependencies
    - Start development server
    - Run tests and linting
    - Git operations

    Never use this tool to perform any harmful or dangerous operations.

    - Use `ls`, `grep` and `tree` tools for file system operations instead of this tool.
    - Use `write` tool to create new files.

    Args:
        command: The command to execute.
        reset_cwd: Whether to reset the current working directory to the project root directory.
        timeout: Maximum time to wait for the command to complete (in seconds). Default is 60.
        
    Returns:
        str: The command output if successful, or error message if failed
    """
    global keep_alive_terminal

    reminders = generate_reminders(runtime)

    # Security checks
    command = command.strip()
    if not command:
        return f"Error: Empty command.{reminders}"

    # Check for dangerous commands
    if is_dangerous_command(command):
        return f"Error: Command blocked for security reasons. This command could cause system damage.{reminders}"

    # Check if command is allowed
    if not is_allowed_command(command):
        return f"Error: Command not allowed. Only basic file operations, package management, and development commands are permitted.{reminders}"

    with terminal_lock:
        try:
            if keep_alive_terminal is None:
                keep_alive_terminal = BashTerminal(project.root_dir)
            elif reset_cwd:
                keep_alive_terminal.close()
                keep_alive_terminal = BashTerminal(project.root_dir)

            output = keep_alive_terminal.execute(command, timeout=timeout)
        except Exception as e:
            output = f"Error executing command: {str(e)}"
            # If terminal crashed, clear it so it can be recreated next time
            if keep_alive_terminal:
                try:
                    keep_alive_terminal.close()
                except Exception:
                    pass
            keep_alive_terminal = None

    return f"```\n{output}\n```{reminders}"
