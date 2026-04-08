from typing import Any

from langchain.messages import AIMessage
from textual.app import App

from mini_opencode import project
from mini_opencode.cli.components import (
    ChatView,
    EditorTabs,
    MessageListView,
    TerminalView,
    TodoListView,
    WorkflowView,
)

from .agent_controller import AgentController


class CommandController:
    """Controller for handling slash commands."""

    SLASH_COMMANDS = [
        "/clear",
        "/resume",
        "/exit",
        "/quit",
        "/mcp-reload",
        "/workflow",
        "/memory",
        "/sandbox",
    ]

    def __init__(self, app: "App[Any]", agent_controller: AgentController):
        self.app = app
        self.agent_controller = agent_controller
        self.history_manager = agent_controller.history_manager

    def handle_slash_command(self, command_line: str) -> None:
        """Parse and execute a slash command."""
        parts = command_line.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "/clear":
            self.app.run_worker(self.handle_clear_command())
        elif cmd == "/resume":
            self.handle_resume_command(args)
        elif cmd == "/exit" or cmd == "/quit":
            self.app.run_worker(self.action_quit())
        elif cmd == "/mcp-reload":
            self.app.run_worker(self.handle_mcp_reload_command())
        elif cmd == "/workflow":
            self.handle_workflow_command(args)
        elif cmd == "/memory":
            self.app.run_worker(self.handle_memory_command(args))
        elif cmd == "/sandbox":
            self.handle_sandbox_command(args)
        else:
            terminal_view = self.app.query_one("#terminal-view", TerminalView)
            terminal_view.write(f"Unknown command: {cmd}\n")

    async def handle_clear_command(self) -> None:
        """Clear the current session and reset the agent."""
        await self.agent_controller.save_current_history()

        self.agent_controller.clear_session()
        self.clear_ui()

        chat_view = self.app.query_one("#chat-view", ChatView)
        chat_view.add_message(
            AIMessage(content="Hello! I'm mini-OpenCode. How can I help you?")
        )

        terminal_view = self.app.query_one("#terminal-view", TerminalView)
        terminal_view.write("Conversation cleared and saved.\n")
        if hasattr(self.app, "focus_input"):
            self.app.focus_input()

    def handle_resume_command(self, args: list[str]) -> None:
        """List sessions or resume a specific session."""
        sessions = self.history_manager.list_sessions(project_root=project.root_dir)
        terminal_view = self.app.query_one("#terminal-view", TerminalView)

        if not args:
            terminal_view.write("Available sessions:\n")
            if not sessions:
                terminal_view.write("- No sessions found.\n")
            else:
                for i, s in enumerate(sessions):
                    terminal_view.write(
                        f"[{i}] {s['id']} - {s['preview']} ({s['timestamp']})\n"
                    )
                terminal_view.write("Use /resume <index> to load a session.\n")
            return

        try:
            idx = int(args[0])
            if 0 <= idx < len(sessions):
                session_id = str(sessions[idx]["id"])
                self.app.run_worker(self.resume_session(session_id))
            else:
                terminal_view.write(f"Invalid session index: {idx}\n")
        except ValueError:
            # Try as session ID
            session_id = args[0]
            self.app.run_worker(self.resume_session(session_id))

    async def resume_session(self, session_id: str) -> None:
        """Resume a previous session."""
        self.agent_controller.is_generating = True
        try:
            await self.agent_controller.save_current_history()

            messages = self.history_manager.load_session(session_id)
            await self.agent_controller.load_session(session_id, messages)  # type: ignore

            self.clear_ui()
            chat_view = self.app.query_one("#chat-view", ChatView)
            for msg in messages:
                chat_view.add_message(msg)  # type: ignore

            terminal_view = self.app.query_one("#terminal-view", TerminalView)
            terminal_view.write(f"Resumed session: {session_id}\n")
        except Exception as e:
            terminal_view = self.app.query_one("#terminal-view", TerminalView)
            terminal_view.write(f"Error resuming session: {e}\n")
        finally:
            self.agent_controller.is_generating = False
            if hasattr(self.app, "focus_input"):
                self.app.focus_input()

    async def handle_mcp_reload_command(self) -> None:
        """Handle the /mcp-reload command to manually reload MCP tools."""
        terminal_view = self.app.query_one("#terminal-view", TerminalView)
        terminal_view.write("$ Reloading MCP tools...\n")
        try:
            await self.agent_controller.reload_mcp_tools()
        except Exception as e:
            terminal_view.write(f"Error: {e}\n")

    # ==================== New Commands ====================

    def handle_workflow_command(self, args: list[str]) -> None:
        """Handle /workflow [on|off|status] command."""
        terminal_view = self.app.query_one("#terminal-view", TerminalView)
        ac = self.agent_controller

        if not args or args[0] == "status":
            terminal_view.write(f"Current agent mode: {ac._mode}\n")
            return

        subcmd = args[0].lower()
        if subcmd == "on":
            if ac._mode == "workflow":
                terminal_view.write("Already in workflow mode.\n")
                return
            result = ac.toggle_mode()
            if result == "workflow":
                terminal_view.write("Switched to workflow mode (Plan-Code-Test-Fix).\n")
            else:
                terminal_view.write(f"{result}\n")
        elif subcmd == "off":
            if ac._mode == "single":
                terminal_view.write("Already in single-agent mode.\n")
                return
            result = ac.toggle_mode()
            if result == "single":
                terminal_view.write("Switched to single-agent mode.\n")
            else:
                terminal_view.write(f"{result}\n")
        else:
            terminal_view.write(
                "Usage: /workflow [on|off|status]\n"
            )

    async def handle_memory_command(self, args: list[str]) -> None:
        """Handle /memory [stats|clear] command."""
        terminal_view = self.app.query_one("#terminal-view", TerminalView)
        ac = self.agent_controller

        subcmd = args[0].lower() if args else "stats"

        if subcmd == "stats":
            if ac._tiered_memory:
                stats = ac._tiered_memory.get_stats()
                terminal_view.write("Memory System: Tiered\n")
                terminal_view.write(
                    f"  Short-term: {stats['short_term_count']}"
                    f"/{stats['short_term_capacity']}\n"
                )
                terminal_view.write(
                    f"  Working:    {stats['working_count']}"
                    f"/{stats['working_capacity']}\n"
                )
                lt_status = "enabled" if stats['long_term_enabled'] else "disabled"
                terminal_view.write(f"  Long-term:  {lt_status}\n")
                terminal_view.write(f"  User ID:    {stats['user_id']}\n")
            elif ac._memory_service:
                status = "enabled" if ac._memory_service.is_enabled else "disabled"
                terminal_view.write(f"Memory System: Flat ({status})\n")
            else:
                terminal_view.write("Memory System: Not initialized\n")
        elif subcmd == "clear":
            if ac._tiered_memory:
                ac._tiered_memory.clear_session()
                terminal_view.write("Short-term memory cleared.\n")
            else:
                terminal_view.write("No tiered memory to clear.\n")
        else:
            terminal_view.write("Usage: /memory [stats|clear]\n")

    def handle_sandbox_command(self, args: list[str]) -> None:
        """Handle /sandbox [status] command."""
        terminal_view = self.app.query_one("#terminal-view", TerminalView)
        ac = self.agent_controller

        if ac._sandbox_manager:
            stats = ac._sandbox_manager.get_stats()
            terminal_view.write("Sandbox Status:\n")
            terminal_view.write(f"  Enabled:   {stats['enabled']}\n")
            terminal_view.write(f"  Provider:  {stats['provider']}\n")
            terminal_view.write(f"  Image:     {stats['image']}\n")
            terminal_view.write(f"  Timeout:   {stats['timeout']}s\n")
            terminal_view.write(f"  Network:   {stats['network_mode']}\n")
            sandbox_id = stats.get('current_sandbox')
            terminal_view.write(
                f"  Container: {sandbox_id or '(none active)'}\n"
            )
        else:
            terminal_view.write("Sandbox: not configured\n")

    # ==================== Existing ====================

    async def action_quit(self) -> None:
        """Save history and exit the application."""
        await self.agent_controller.save_current_history()
        self.app.exit()

    def clear_ui(self) -> None:
        """Clear all UI components."""
        chat_view = self.app.query_one("#chat-view", ChatView)
        message_list = chat_view.query_one("#message-list", MessageListView)
        message_list.clear()

        editor_tabs = self.app.query_one("#editor-tabs", EditorTabs)
        editor_tabs.clear_tabs()

        terminal_view = self.app.query_one("#terminal-view", TerminalView)
        terminal_view.clear()

        todo_list_view = self.app.query_one("#todo-list-view", TodoListView)
        todo_list_view.update_items([])

        try:
            workflow_view = self.app.query_one("#workflow-view", WorkflowView)
            workflow_view.clear_workflow()
        except Exception:
            pass
