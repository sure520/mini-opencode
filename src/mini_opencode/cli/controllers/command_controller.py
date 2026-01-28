from langchain.messages import AIMessage
from textual.app import App

from mini_opencode import project
from mini_opencode.cli.components import (
    ChatView,
    EditorTabs,
    MessageListView,
    TerminalView,
    TodoListView,
)

from .agent_controller import AgentController


class CommandController:
    """Controller for handling slash commands."""

    SLASH_COMMANDS = ["/clear", "/resume", "/exit", "/quit"]

    def __init__(self, app: "App", agent_controller: AgentController):
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
                session_id = sessions[idx]["id"]
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
            await self.agent_controller.load_session(session_id, messages)

            self.clear_ui()
            chat_view = self.app.query_one("#chat-view", ChatView)
            # MessageListView.clear already handles messages, we just need to add them back
            for msg in messages:
                chat_view.add_message(msg)

            terminal_view = self.app.query_one("#terminal-view", TerminalView)
            terminal_view.write(f"Resumed session: {session_id}\n")
        except Exception as e:
            terminal_view = self.app.query_one("#terminal-view", TerminalView)
            terminal_view.write(f"Error resuming session: {e}\n")
        finally:
            self.agent_controller.is_generating = False
            if hasattr(self.app, "focus_input"):
                self.app.focus_input()

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
