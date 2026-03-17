import asyncio
from typing import Any

from langchain.messages import AIMessage, HumanMessage
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, TabbedContent, TabPane, TextArea
from textual.worker import Worker

from mini_opencode import project
from mini_opencode.cli.components import (
    ChatInput,
    ChatView,
    EditorTabs,
    SuggestionView,
    TerminalView,
    TodoListView,
)
from mini_opencode.cli.controllers import (
    AgentController,
    CommandController,
    SuggestionController,
)
from mini_opencode.cli.theme import DARK_THEME, LIGHT_THEME, is_dark_mode


class ConsoleApp(App[Any]):
    """The main application for mini-OpenCode."""

    TITLE = "mini-OpenCode"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("ctrl+g", "stop_agent", "Stop", show=False),
    ]
    CSS = """
    Screen {
        layout: horizontal;
        background: $background;
    }

    Header {
        background: $primary;
        color: $foreground;
    }

    Footer {
        background: $surface;
        color: $secondary;
    }

    #left-panel {
        width: 3fr;
        background: $panel;
    }

    #right-panel {
        width: 4fr;
        background: $boost;
    }

    #editor-view {
        height: 70%;
    }

    #bottom-right-tabs {
        height: 30%;
        background: $panel;
    }

    #bottom-right-tabs TabPane {
        padding: 0;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_generating = False
        self._current_worker: Worker | None = None

        # Initialize controllers
        self.agent_controller = AgentController(self)
        self.command_controller = CommandController(self, self.agent_controller)
        self.suggestion_controller = SuggestionController(self, self.command_controller)

    @property
    def is_generating(self) -> bool:
        return self._is_generating

    @is_generating.setter
    def is_generating(self, value: bool) -> None:
        self._is_generating = value
        try:
            chat_view = self.query_one("#chat-view", ChatView)
            chat_view.is_generating = value
            chat_view.disabled = value
            try:
                terminal_view = self.query_one("#terminal-view", TerminalView)
                terminal_view.write(f"\n[DEBUG] App.is_generating={value}, chat_view.is_generating={chat_view.is_generating}\n")
            except Exception:
                pass
        except Exception as e:
            # Widget might not be mounted yet
            pass

    def compose(self) -> ComposeResult:
        yield Header(id="header")
        with Vertical(id="left-panel"):
            yield ChatView(id="chat-view")
        with Vertical(id="right-panel"):
            yield EditorTabs(id="editor-tabs")
            with TabbedContent(id="bottom-right-tabs"):
                with TabPane(id="terminal-tab", title="Terminal"):
                    yield SuggestionView(id="suggestion-view")
                    yield TerminalView(id="terminal-view")
                with TabPane(id="todo-tab", title="To-do"):
                    yield TodoListView(id="todo-list-view")
        yield Footer(id="footer")

    def focus_input(self) -> None:
        chat_view = self.query_one("#chat-view", ChatView)
        chat_view.focus_input()

    def on_mount(self) -> None:
        self.register_theme(DARK_THEME)
        self.register_theme(LIGHT_THEME)
        self.theme = "dark" if is_dark_mode() else "light"
        self.sub_title = str(project.root_dir)
        self.is_generating = True
        editor_tabs = self.query_one("#editor-tabs", EditorTabs)
        editor_tabs.open_welcome()

        asyncio.create_task(self.agent_controller.init_agent())
        self.set_interval(2.0, self._check_system_theme)

    def _check_system_theme(self) -> None:
        """Check and update the theme based on system settings."""
        new_theme = "dark" if is_dark_mode() else "light"
        if self.theme != new_theme:
            self.theme = new_theme
            editor_tabs = self.query_one("#editor-tabs", EditorTabs)
            editor_tabs.refresh_code_theme()

    @on(ChatInput.Submitted)
    def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        if not self.is_generating:
            user_input = event.value.strip()
            if user_input:
                # Clear suggestions when submitting
                suggestion_view = self.query_one("#suggestion-view", SuggestionView)
                suggestion_view.set_suggestions([])
                chat_view = self.query_one("#chat-view", ChatView)
                chat_input = chat_view.query_one("#chat-input", ChatInput)
                chat_input.suggestions_active = False

                if user_input.startswith("/"):
                    self.command_controller.handle_slash_command(user_input)
                    return

                user_message = HumanMessage(content=user_input)
                worker = self.run_worker(
                    self.agent_controller.handle_user_input(user_message)
                )
                self._current_worker = worker

    @on(TextArea.Changed)
    def on_input_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id != "chat-textarea":
            return
        self.suggestion_controller.update_suggestions(event.text_area.text)

    @on(ChatInput.NavigateSuggestion)
    def on_navigate_suggestion(self, event: ChatInput.NavigateSuggestion) -> None:
        self.suggestion_controller.navigate_suggestions(event.direction)

    @on(ChatInput.SelectSuggestion)
    def on_select_suggestion(self, event: ChatInput.SelectSuggestion) -> None:
        self.suggestion_controller.select_suggestion()

    @on(ChatInput.StopRequested)
    def on_stop_requested(self, event: ChatInput.StopRequested) -> None:
        if self._current_worker and not self._current_worker.is_done:
            # 立即更新 UI，让用户看到按钮状态变化
            self.is_generating = False
            self.agent_controller._cancelled = True
            self._current_worker.cancel()
            self._current_worker = None
            terminal_view = self.query_one("#terminal-view", TerminalView)
            terminal_view.write("\n$ [Cancelled by user]")
            chat_view = self.query_one("#chat-view", ChatView)
            chat_view.add_message(AIMessage(content="**Operation cancelled by user.**"))
            self.focus_input()

    async def action_quit(self) -> None:
        await self.command_controller.action_quit()

    async def action_stop_agent(self) -> None:
        """Stop the currently running agent operation."""
        if self._current_worker and not self._current_worker.is_done:
            # 立即更新 UI，让用户看到按钮状态变化
            self.is_generating = False
            self.agent_controller._cancelled = True
            self._current_worker.cancel()
            self._current_worker = None
            terminal_view = self.query_one("#terminal-view", TerminalView)
            terminal_view.write("\n$ [Cancelled by user]")
            chat_view = self.query_one("#chat-view", ChatView)
            chat_view.add_message(AIMessage(content="**Operation cancelled by user.**"))
            self.focus_input()

    def on_unmount(self) -> None:
        """Clean up resources when the application exits."""
        # 停止配置文件监听器
        if hasattr(self, "agent_controller"):
            asyncio.create_task(self.agent_controller.stop_config_watch())
