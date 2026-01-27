import asyncio
import datetime
import re

from langchain.messages import (
    AIMessage,
    AIMessageChunk,
    AnyMessage,
    HumanMessage,
    ToolMessage,
)
from langgraph.checkpoint.memory import MemorySaver
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, TabbedContent, TabPane

from mini_opencode import project
from mini_opencode.agents import create_coding_agent
from mini_opencode.cli.components import MessageListView
from mini_opencode.tools import load_mcp_tools

from .components import ChatInput, ChatView, EditorTabs, TerminalView, TodoListView
from .history import HistoryManager
from .theme import DARK_THEME, LIGHT_THEME, is_dark_mode


class ConsoleApp(App):
    """The main application for mini-OpenCode."""

    TITLE = "mini-OpenCode"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False),
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
        self._mcp_tools: list = []
        self._terminal_tool_calls: list[str] = []
        self._file_modification_tool_calls: dict[str, str] = {}
        self._checkpointer = MemorySaver()
        self._history_manager = HistoryManager()
        self._session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    @property
    def is_generating(self) -> bool:
        return self._is_generating

    @is_generating.setter
    def is_generating(self, value: bool) -> None:
        self._is_generating = value
        chat_view = self.query_one("#chat-view", ChatView)
        chat_view.is_generating = value
        chat_view.disabled = value

    def compose(self) -> ComposeResult:
        yield Header(id="header")
        with Vertical(id="left-panel"):
            yield ChatView(id="chat-view")
        with Vertical(id="right-panel"):
            yield EditorTabs(id="editor-tabs")
            with TabbedContent(id="bottom-right-tabs"):
                with TabPane(id="terminal-tab", title="Terminal"):
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
        self.sub_title = project.root_dir
        self.is_generating = True
        editor_tabs = self.query_one("#editor-tabs", EditorTabs)
        editor_tabs.open_welcome()

        asyncio.create_task(self._init_agent())
        self.set_interval(2.0, self._check_system_theme)

    async def _init_agent(self) -> None:
        terminal_view = self.query_one("#terminal-view", TerminalView)
        terminal_view.write("$ Loading MCP tools...")
        try:
            self._mcp_tools = await load_mcp_tools()
            tool_count = len(self._mcp_tools)
            if tool_count > 0:
                terminal_view.write(
                    f"- {tool_count} tool{' is' if tool_count == 1 else 's are'} loaded.\n",
                    True,
                )
            else:
                terminal_view.write("- No tools found.\n", True)
        except Exception:
            terminal_view.write("- Error loading tools.\n", True)

        terminal_view.write("$ Loading agent...")
        try:
            self._coding_agent = create_coding_agent(
                plugin_tools=self._mcp_tools, checkpointer=self._checkpointer
            )
            terminal_view.write("- Agent loaded successfully.\n", True)
            self.is_generating = False
            self.focus_input()
        except Exception as e:
            # Fatal error, exit the application
            terminal_view.write(f"- Error loading agent: {e}\n", True)
            await asyncio.sleep(3)
            self.exit(1)

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
                if user_input.startswith("/"):
                    self._handle_slash_command(user_input)
                    return

                user_message = HumanMessage(content=user_input)
                self._handle_user_input(user_message)

    async def action_quit(self) -> None:
        await self._save_current_history()
        self.exit()

    def _handle_slash_command(self, command_line: str) -> None:
        parts = command_line.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "/clear":
            self.run_worker(self._handle_clear_command())
        elif cmd == "/resume":
            self._handle_resume_command(args)
        elif cmd == "/exit" or cmd == "/quit":
            self.run_worker(self.action_quit())
        else:
            terminal_view = self.query_one("#terminal-view", TerminalView)
            terminal_view.write(f"Unknown command: {cmd}\n")

    async def _handle_clear_command(self) -> None:
        await self._save_current_history()

        self._checkpointer = MemorySaver()
        self._coding_agent = create_coding_agent(
            plugin_tools=self._mcp_tools, checkpointer=self._checkpointer
        )

        self._clear_ui()
        chat_view = self.query_one("#chat-view", ChatView)
        chat_view.add_message(
            AIMessage(content="Hello! I'm mini-OpenCode. How can I help you?")
        )

        self._session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        terminal_view = self.query_one("#terminal-view", TerminalView)
        terminal_view.write("Conversation cleared and saved.\n")
        self.focus_input()

    def _handle_resume_command(self, args: list[str]) -> None:
        sessions = self._history_manager.list_sessions()
        terminal_view = self.query_one("#terminal-view", TerminalView)

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
                self.run_worker(self._resume_session(session_id))
            else:
                terminal_view.write(f"Invalid session index: {idx}\n")
        except ValueError:
            # Try as session ID
            session_id = args[0]
            self.run_worker(self._resume_session(session_id))

    async def _resume_session(self, session_id: str) -> None:
        self.is_generating = True
        try:
            await self._save_current_history()

            self._checkpointer = MemorySaver()
            self._coding_agent = create_coding_agent(
                plugin_tools=self._mcp_tools, checkpointer=self._checkpointer
            )

            config = {"configurable": {"thread_id": "thread_1"}}
            messages = self._history_manager.load_session(session_id)
            await self._coding_agent.aupdate_state(config, {"messages": messages})

            self._clear_ui()
            chat_view = self.query_one("#chat-view", ChatView)
            # MessageListView.clear already handles messages, we just need to add them back
            for msg in messages:
                chat_view.add_message(msg)

            self._session_id = session_id

            terminal_view = self.query_one("#terminal-view", TerminalView)
            terminal_view.write(f"Resumed session: {session_id}\n")
        except Exception as e:
            terminal_view = self.query_one("#terminal-view", TerminalView)
            terminal_view.write(f"Error resuming session: {e}\n")
        finally:
            self.is_generating = False
            self.focus_input()

    def _clear_ui(self) -> None:
        self._terminal_tool_calls = []
        self._file_modification_tool_calls = {}

        chat_view = self.query_one("#chat-view", ChatView)
        message_list = chat_view.query_one("#message-list", MessageListView)
        message_list.clear()

        editor_tabs = self.query_one("#editor-tabs", EditorTabs)
        editor_tabs.clear_tabs()

        terminal_view = self.query_one("#terminal-view", TerminalView)
        terminal_view.clear()

        todo_list_view = self.query_one("#todo-list-view", TodoListView)
        todo_list_view.update_items([])

    async def _save_current_history(self) -> None:
        if not hasattr(self, "_coding_agent") or self._coding_agent is None:
            return

        config = {"configurable": {"thread_id": "thread_1"}}
        try:
            state = await self._coding_agent.aget_state(config)
            messages = state.values.get("messages", [])
            if messages:
                self._history_manager.save_session(messages, self._session_id)
        except Exception:
            pass

    @work(exclusive=True, thread=False)
    async def _handle_user_input(self, user_message: HumanMessage) -> None:
        self._process_outgoing_message(user_message)
        self.is_generating = True
        try:
            current_ai_message: AIMessageChunk | None = None
            async for event_type, chunk in self._coding_agent.astream(
                {"messages": [user_message]},
                stream_mode=["messages", "updates"],
                config={"recursion_limit": 100, "thread_id": "thread_1"},
            ):
                if event_type == "messages":
                    message_chunk, _ = chunk
                    if isinstance(message_chunk, AIMessageChunk):
                        if current_ai_message is None:
                            current_ai_message = message_chunk
                            self._process_incoming_message(current_ai_message)
                        else:
                            current_ai_message += message_chunk
                            # During streaming, don't update tool call widgets to avoid partial parsing errors
                            self._update_incoming_message(
                                current_ai_message, update_tools=False
                            )

                elif event_type == "updates":
                    # Node finished. Reset current_ai_message for next potential AI response
                    current_ai_message = None

                    roles = chunk.keys()
                    for role in roles:
                        messages: list[AnyMessage] = chunk[role].get("messages", [])
                        for message in messages:
                            if isinstance(message, AIMessage):
                                # Update with final message (includes complete tool calls)
                                self._update_incoming_message(
                                    message, update_tools=True
                                )
                                if message.tool_calls:
                                    self._process_tool_call_message(message)
                            elif isinstance(message, ToolMessage):
                                # Tool results are not streamed, add them normally
                                self._process_incoming_message(message)
                                self._process_tool_message(message)
        except Exception as e:
            error_message = AIMessage(
                content=f"❌ **An error occurred:** {str(e)}\n\nPlease try again."
            )
            self._process_incoming_message(error_message)
        finally:
            await self._save_current_history()
            self.is_generating = False
            self.focus_input()

    def _process_outgoing_message(self, message: HumanMessage) -> None:
        chat_view = self.query_one("#chat-view", ChatView)
        chat_view.add_message(message)

    def _process_incoming_message(self, message: AnyMessage) -> None:
        chat_view = self.query_one("#chat-view", ChatView)
        chat_view.add_message(message)

    def _update_incoming_message(
        self, message: AnyMessage, update_tools: bool = True
    ) -> None:
        chat_view = self.query_one("#chat-view", ChatView)
        chat_view.update_message(message, update_tools=update_tools)

    def _format_tool_call_preview(self, tool_name: str, tool_args: dict) -> str | None:
        if tool_name == "bash":
            command = tool_args.get("command")
            return f"$ {command}" if command else "$ bash"
        if tool_name == "tree":
            path = tool_args.get("path") or "."
            max_depth = tool_args.get("max_depth")
            depth_part = f" --max-depth={max_depth}" if max_depth is not None else ""
            return f"$ tree {path}{depth_part}"
        if tool_name == "grep":
            pattern = tool_args.get("pattern")
            path = tool_args.get("path")
            glob = tool_args.get("glob")
            output_mode = tool_args.get("output_mode")
            parts: list[str] = ["$ grep"]
            if pattern:
                parts.append(str(pattern))
            if path:
                parts.append(str(path))
            if glob:
                parts.append(f"--glob={glob}")
            if output_mode:
                parts.append(f"--output={output_mode}")
            return " ".join(parts)
        if tool_name == "ls":
            path = tool_args.get("path") or "."
            match = tool_args.get("match")
            ignore = tool_args.get("ignore")
            parts = ["$ ls", str(path)]
            if match:
                parts.append(f"--match={match}")
            if ignore:
                parts.append(f"--ignore={ignore}")
            return " ".join(parts)
        return None

    def _process_tool_call_message(self, message: AIMessage) -> None:
        terminal_view = self.query_one("#terminal-view", TerminalView)
        todo_list_view = self.query_one("#todo-list-view", TodoListView)
        editor_tabs = self.query_one("#editor-tabs", EditorTabs)
        bottom_right_tabs = self.query_one("#bottom-right-tabs", TabbedContent)
        for tool_call in message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            preview = self._format_tool_call_preview(tool_name, tool_args)
            if tool_name in {"bash", "tree", "grep", "ls"}:
                self._terminal_tool_calls.append(tool_call["id"])
                terminal_view.write(preview or f"$ {tool_name}")
                bottom_right_tabs.active = "terminal-tab"
            elif tool_name == "todo_write":
                bottom_right_tabs.active = "todo-tab"
                todo_list_view.update_items(tool_args["todos"])
            elif tool_name == "read":
                editor_tabs.open_file(tool_args["path"])
            elif tool_name == "write":
                editor_tabs.open_file(tool_args["path"], tool_args.get("content"))
                self._file_modification_tool_calls[tool_call["id"]] = tool_args["path"]
            elif tool_name == "edit":
                editor_tabs.open_file(tool_args["path"])
                self._file_modification_tool_calls[tool_call["id"]] = tool_args["path"]

    def _process_tool_message(self, message: ToolMessage) -> None:
        terminal_view = self.query_one("#terminal-view", TerminalView)
        if message.tool_call_id in self._terminal_tool_calls:
            output = self._extract_code(message.content)
            terminal_view.write(
                output if output.strip() != "" else "\n(empty)\n",
                muted=True,
            )
            self._terminal_tool_calls.remove(message.tool_call_id)
        elif self._file_modification_tool_calls.get(message.tool_call_id):
            path = self._file_modification_tool_calls[message.tool_call_id]
            del self._file_modification_tool_calls[message.tool_call_id]
            editor_tabs = self.query_one("#editor-tabs", EditorTabs)
            editor_tabs.open_file(path)

    def _extract_code(self, text: str) -> str:
        match = re.search(r"```(.*)```", text, re.DOTALL)
        if match:
            return match.group(1)
        return text


app = ConsoleApp()
