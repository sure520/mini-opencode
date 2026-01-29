from datetime import datetime

from textual.app import App
from textual.widgets import TabbedContent

from mini_opencode import project
from mini_opencode.cli.components import (
    ChatInput,
    ChatView,
    SuggestionView,
    TerminalView,
)

from .command_controller import CommandController


class SuggestionController:
    """Controller for handling input suggestions."""

    def __init__(self, app: "App", command_controller: "CommandController"):
        self.app = app
        self.command_controller = command_controller

    def update_suggestions(self, text: str) -> None:
        """Update suggestions based on input text."""
        suggestion_view = self.app.query_one("#suggestion-view", SuggestionView)
        chat_view = self.app.query_one("#chat-view", ChatView)
        chat_input = chat_view.query_one("#chat-input", ChatInput)

        # Only show suggestions if text starts with / and has no spaces (first word)
        if text.startswith("/") and " " not in text:
            query = text.lower()
            matches = [
                cmd
                for cmd in self.command_controller.SLASH_COMMANDS
                if cmd.startswith(query)
            ]
            suggestion_view.set_suggestions(matches)
            chat_input.suggestions_active = len(matches) > 0
            if matches:
                self.app.query_one(
                    "#bottom-right-tabs", TabbedContent
                ).active = "terminal-tab"
        elif text.startswith("/resume "):
            # Show session suggestions
            sessions = self.command_controller.history_manager.list_sessions(
                project_root=project.root_dir
            )
            if sessions:
                # Format sessions for SuggestionView
                session_suggestions = []
                for s in sessions:
                    dt = datetime.fromisoformat(s["timestamp"])
                    timestamp = dt.strftime("%Y-%m-%d %H:%M")
                    display_text = f"{timestamp} - {s['preview'][:30]}..."
                    session_suggestions.append(
                        {"text": display_text, "value": s["id"], "type": "session"}
                    )

                suggestion_view.set_suggestions(session_suggestions)
                chat_input.suggestions_active = True
                self.app.query_one(
                    "#bottom-right-tabs", TabbedContent
                ).active = "terminal-tab"
            else:
                suggestion_view.set_suggestions([])
                chat_input.suggestions_active = False
                # Only show the "No sessions" message when exactly typing "/resume "
                # to avoid spamming while typing filters
                if text == "/resume ":
                    terminal_view = self.app.query_one("#terminal-view", TerminalView)
                    terminal_view.write("No sessions available to resume.\n")
                    self.app.query_one(
                        "#bottom-right-tabs", TabbedContent
                    ).active = "terminal-tab"
        else:
            suggestion_view.set_suggestions([])
            chat_input.suggestions_active = False

    def navigate_suggestions(self, direction: int) -> None:
        """Move selection in suggestions list."""
        suggestion_view = self.app.query_one("#suggestion-view", SuggestionView)
        suggestion_view.move_selection(direction)

    def select_suggestion(self) -> None:
        """Handle suggestion selection."""
        suggestion_view = self.app.query_one("#suggestion-view", SuggestionView)
        selected = suggestion_view.get_selected()
        if selected:
            chat_view = self.app.query_one("#chat-view", ChatView)
            chat_input = chat_view.query_one("#chat-input", ChatInput)
            value = selected["value"]
            suggestion_type = selected.get("type")

            if suggestion_type == "session":
                # Execute resume with the session ID
                self.app.run_worker(self.command_controller.resume_session(value))
                chat_input.text = ""
            else:
                # Normal slash command
                chat_input.text = value
                if value == "/resume":
                    # Check if sessions exist before prompting
                    sessions = self.command_controller.history_manager.list_sessions(
                        project_root=project.root_dir
                    )
                    if not sessions:
                        terminal_view = self.app.query_one(
                            "#terminal-view", TerminalView
                        )
                        terminal_view.write("No sessions available to resume.\n")
                        self.app.query_one(
                            "#bottom-right-tabs", TabbedContent
                        ).active = "terminal-tab"
                        chat_input.text = ""  # Clear instead of "/resume "
                    else:
                        # Add a space to trigger session suggestions
                        chat_input.text = "/resume "
                        chat_input.move_cursor((0, len(chat_input.text)))
                else:
                    self.command_controller.handle_slash_command(value)
                    chat_input.text = ""

            chat_input.suggestions_active = False
            suggestion_view.set_suggestions([])
            chat_input.focus()
