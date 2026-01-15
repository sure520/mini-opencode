import os
import re
import uuid

import pexpect


class BashTerminal:
    """A keep-alive terminal for executing bash commands."""

    def __init__(self, cwd=None):
        """
        Initialize BashTerminal

        Args:
            cwd: Initial working directory, defaults to current directory
        """
        self.cwd = cwd or os.getcwd()

        # Start bash shell with a larger search window for pexpect
        self.shell = pexpect.spawn(
            "/bin/bash", encoding="utf-8", echo=False, searchwindowsize=1024 * 10
        )

        # Set custom prompt for easy command completion detection
        # Using a UUID to make the prompt extremely unlikely to appear in command output
        self.prompt = f"BASH_TERMINAL_PROMPT_{uuid.uuid4().hex[:8]}> "
        self.shell.sendline(f'PS1="{self.prompt}"')
        self.shell.expect(self.prompt, timeout=5)
        # Set secondary prompt to empty to avoid leaking it in multi-line commands
        self.shell.sendline('PS2=""')
        self.shell.expect(self.prompt, timeout=5)

        # Change to specified directory
        if cwd:
            self.execute(f'cd "{self.cwd}"')

    def execute(self, command, timeout=60):
        """
        Execute bash command and return output

        Args:
            command: Command to execute
            timeout: Command execution timeout (seconds)

        Returns:
            Command output result (string)
        """
        if not command.strip():
            return ""

        # Ensure command is treated as a single block to avoid multiple prompts
        # and ensure we wait for the very end of all commands.
        # We use a brace group { ... ; } to execute in the current shell context
        # so that environment variables and CWD changes are preserved.
        # Adding newlines around the command to handle cases where the command
        # might end with a comment.
        wrapped_command = f"{{\n{command.strip()}\n}}"
        self.shell.sendline(wrapped_command)

        try:
            # Wait for prompt to appear, indicating command completion
            self.shell.expect(self.prompt, timeout=timeout)
        except pexpect.TIMEOUT:
            return f"Error: Command timed out after {timeout} seconds. Current output:\n{self.shell.before}"
        except pexpect.EOF:
            return f"Error: Terminal session ended unexpectedly. Current output:\n{self.shell.before}"

        # Get output, removing command itself and prompt
        output = self.shell.before

        # Clean output: remove command echo if it exists
        # In some environments, even with echo=False, command may still echo
        lines = output.splitlines()

        # Remove echoed command lines from the beginning of the output
        # If echo is on, the shell will echo the wrapped command block
        wrapped_lines = wrapped_command.strip().splitlines()
        if len(lines) >= len(wrapped_lines):
            match = True
            for i in range(len(wrapped_lines)):
                if lines[i].strip() != wrapped_lines[i].strip():
                    match = False
                    break
            if match:
                lines = lines[len(wrapped_lines) :]
        elif lines and lines[0].strip() == command.strip():
            lines = lines[1:]

        # Join lines back, preserving internal indentation but stripping overall leading/trailing newlines
        result = "\n".join(lines).strip("\r\n")

        # Remove terminal control characters (ANSI escape sequences)
        # Using a more comprehensive regex for ANSI escape sequences
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        result = ansi_escape.sub("", result)

        return result

    def getcwd(self):
        """
        Get current working directory

        Returns:
            Absolute path of current working directory
        """
        result = self.execute("pwd")
        return result.strip()

    def close(self):
        """Close shell session"""
        if self.shell.isalive():
            self.shell.sendline("exit")
            self.shell.close()

    def __del__(self):
        """Destructor, ensure shell is closed"""
        self.close()

    def __enter__(self):
        """Support with statement"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Support with statement"""
        self.close()
