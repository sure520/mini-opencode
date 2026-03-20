import asyncio
import datetime
import re
from typing import Any

from langchain.messages import (
    AIMessage,
    AIMessageChunk,
    AnyMessage,
    HumanMessage,
    ToolMessage,
)
from langgraph.checkpoint.memory import MemorySaver
from textual.app import App
from textual.widgets import TabbedContent

from mini_opencode import project
from mini_opencode.agents import create_coding_agent
from mini_opencode.cli.components import (
    ChatView,
    EditorTabs,
    TerminalView,
    TodoListView,
)
from mini_opencode.cli.history import HistoryManager
from mini_opencode.config import get_config_section
from mini_opencode.services import MemoryService
from mini_opencode.tools.mcp.mcp_manager import get_mcp_manager


class AgentController:
    """Controller for managing the AI agent and its interactions."""

    def __init__(self, app: 'App[Any]'):
        self.app = app
        self._coding_agent = None
        self._mcp_tools: list[Any] = []
        self._terminal_tool_calls: list[str] = []
        self._file_modification_tool_calls: dict[str, str] = {}
        self._checkpointer = MemorySaver()
        self._session_id = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        self.history_manager = HistoryManager()
        self._cancelled = False
        self._mcp_manager = get_mcp_manager()
        self._config_watch_enabled = False
        self._memory_service: MemoryService | None = None
        self._current_user_message: HumanMessage | None = None
        self._current_ai_message: AIMessage | None = None

    @property
    def is_generating(self) -> bool:
        """Check if the agent is currently generating."""
        if hasattr(self.app, "is_generating"):
            return bool(self.app.is_generating)
        return False

    @is_generating.setter
    def is_generating(self, value: bool) -> None:
        """Set the generating state on the app."""
        if hasattr(self.app, "is_generating"):
            self.app.is_generating = value

    async def init_agent(self, enable_config_watch: bool = True) -> None:
        """Initialize the agent and load tools."""
        terminal_view = self.app.query_one("#terminal-view", TerminalView)
        terminal_view.write("$ Loading MCP tools...")
        try:
            self._mcp_tools = await self._mcp_manager.load_tools()
            tool_count = len(self._mcp_tools)
            if tool_count > 0:
                terminal_view.write(
                    f"- {tool_count} tool"
                    f"{' is' if tool_count == 1 else 's are'} loaded.\n",
                    True,
                )
            else:
                terminal_view.write("- No tools found.\n", True)
        except Exception:
            terminal_view.write("- Error loading tools.\n", True)

        # 注册工具更新回调
        self._mcp_manager.on_tools_updated(self._on_tools_updated)

        # 启动配置文件监听器
        if enable_config_watch:
            await self.start_config_watch()

        # Initialize memory service
        memory_enabled = get_config_section(['memory', 'enabled'])
        memory_enabled = memory_enabled if isinstance(memory_enabled, bool) else True
        memory_user_id = get_config_section(['memory', 'user_id'])
        memory_user_id = (
            memory_user_id if isinstance(memory_user_id, str) else 'default'
        )
        self._memory_service = MemoryService(
            enabled=memory_enabled, user_id=memory_user_id
        )
        if self._memory_service.is_enabled:
            terminal_view.write(
                f"- Memory service enabled for user: {memory_user_id}\n",
                True,
            )
        else:
            terminal_view.write("- Memory service disabled.\n", True)

        terminal_view.write("$ Loading agent...")
        try:
            self._coding_agent = create_coding_agent(
                plugin_tools=self._mcp_tools,
                checkpointer=self._checkpointer,
                memory_service=self._memory_service,
            )
            terminal_view.write("- Agent loaded successfully.\n", True)
            self.is_generating = False
            if hasattr(self.app, 'focus_input'):
                self.app.focus_input()
        except Exception as e:
            # Fatal error, exit the application
            terminal_view.write(f"- Error loading agent: {e}\n", True)
            await asyncio.sleep(3)
            self.app.exit(1)

    async def handle_user_input(self, user_message: HumanMessage) -> None:
        """Handle user input and stream the response."""
        self._cancelled = False
        self._current_user_message = user_message
        self._current_ai_message = None
        self.process_outgoing_message(user_message)
        self.is_generating = True

        # Yield control to allow cancellation to be detected immediately
        await asyncio.sleep(0)

        try:
            if not self._coding_agent:
                error_message = AIMessage(
                    content=(
                        "❌ **Agent not initialized.** "
                        "Please restart the application."
                    )
                )
                self.process_incoming_message(error_message)
                return

            current_ai_message: AIMessageChunk | None = None
            try:
                async for event_type, chunk in self._coding_agent.astream(
                    {"messages": [user_message]},
                    stream_mode=["messages", "updates"],
                    config={"recursion_limit": 100, "thread_id": "thread_1"},
                ):
                    # Check cancellation before processing each chunk
                    if self._cancelled:
                        break

                    # Yield control to allow cancellation to be detected immediately
                    await asyncio.sleep(0)

                    if event_type == "messages":
                        message_chunk, _ = chunk
                        if isinstance(message_chunk, AIMessageChunk):
                            if current_ai_message is None:
                                current_ai_message = message_chunk
                                self.process_incoming_message(current_ai_message)
                            else:
                                current_ai_message += message_chunk
                                self.update_incoming_message(
                                    current_ai_message, update_tools=False
                                )

                    elif event_type == 'updates':
                        current_ai_message = None

                        roles = chunk.keys()
                        for role in roles:
                            if self._cancelled:
                                break
                            messages: list[AnyMessage] = chunk[role].get('messages', [])
                            for message in messages:
                                if self._cancelled:
                                    break
                                # Yield control before processing each message
                                await asyncio.sleep(0)
                                if isinstance(message, AIMessage):
                                    self._current_ai_message = message
                                    self.update_incoming_message(
                                        message, update_tools=True
                                    )
                                    if message.tool_calls:
                                        self.process_tool_call_message(message)
                                elif isinstance(message, ToolMessage):
                                    self.process_incoming_message(message)
                                    self.process_tool_message(message)
            except asyncio.CancelledError:
                self._cancelled = True
                terminal_view = self.app.query_one("#terminal-view", TerminalView)
                terminal_view.write("\n$ [Operation cancelled]")
                self.is_generating = False
                if hasattr(self.app, "focus_input"):
                    self.app.focus_input()
                return
        except asyncio.CancelledError:
            self._cancelled = True
            terminal_view = self.app.query_one("#terminal-view", TerminalView)
            terminal_view.write("\n$ [Operation cancelled]")
            self.is_generating = False
            if hasattr(self.app, "focus_input"):
                self.app.focus_input()
            return
        except Exception as e:
            if not self._cancelled:
                error_message = AIMessage(
                    content=f"❌ **An error occurred:** {str(e)}\n\nPlease try again."
                )
                self.process_incoming_message(error_message)
        finally:
            self.is_generating = False
            if not self._cancelled:
                await self.save_current_history()
                # Save conversation to memory
                await self._save_conversation_to_memory()
            if hasattr(self.app, 'focus_input'):
                self.app.focus_input()

    def process_outgoing_message(self, message: HumanMessage) -> None:
        """Add user message to chat view."""
        if self._cancelled:
            return
        chat_view = self.app.query_one("#chat-view", ChatView)
        chat_view.add_message(message)

    def process_incoming_message(self, message: AnyMessage) -> None:
        """Add AI or tool message to chat view."""
        if self._cancelled:
            return
        chat_view = self.app.query_one("#chat-view", ChatView)
        chat_view.add_message(message)

    def update_incoming_message(
        self, message: AnyMessage, update_tools: bool = True
    ) -> None:
        """Update the last message in chat view."""
        if self._cancelled:
            return
        chat_view = self.app.query_one("#chat-view", ChatView)
        chat_view.update_message(message, update_tools=update_tools)

    def process_tool_call_message(self, message: AIMessage) -> None:
        """Handle tool calls from the agent."""
        if self._cancelled:
            return
        terminal_view = self.app.query_one("#terminal-view", TerminalView)
        todo_list_view = self.app.query_one("#todo-list-view", TodoListView)
        editor_tabs = self.app.query_one("#editor-tabs", EditorTabs)
        bottom_right_tabs = self.app.query_one("#bottom-right-tabs", TabbedContent)

        for tool_call in message.tool_calls:
            if self._cancelled:
                break
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            preview = self._format_tool_call_preview(tool_name, tool_args)
            tool_id = tool_call.get("id")
            if tool_name in {"bash", "tree", "grep", "ls"} and tool_id:
                self._terminal_tool_calls.append(tool_id)
                terminal_view.write(preview or f"$ {tool_name}")
                bottom_right_tabs.active = "terminal-tab"
            elif tool_name == "todo_write":
                bottom_right_tabs.active = "todo-tab"
                todo_list_view.update_items(tool_args["todos"])
            elif tool_name == "read":
                editor_tabs.open_file(tool_args["path"])
            elif tool_name == "write":
                editor_tabs.open_file(tool_args["path"], tool_args.get("content"))
                if tool_id:
                    self._file_modification_tool_calls[tool_id] = tool_args["path"]
            elif tool_name == "edit":
                editor_tabs.open_file(tool_args["path"])
                if tool_id:
                    self._file_modification_tool_calls[tool_id] = tool_args["path"]

    def process_tool_message(self, message: ToolMessage) -> None:
        """Handle tool results."""
        if self._cancelled:
            return
        terminal_view = self.app.query_one("#terminal-view", TerminalView)
        tool_call_id = message.tool_call_id
        if tool_call_id and tool_call_id in self._terminal_tool_calls:
            output = self._extract_code(str(message.content))
            terminal_view.write(
                output if output.strip() != "" else "\n(empty)\n",
                muted=True,
            )
            self._terminal_tool_calls.remove(tool_call_id)
        elif tool_call_id and tool_call_id in self._file_modification_tool_calls:
            path = self._file_modification_tool_calls[tool_call_id]
            del self._file_modification_tool_calls[tool_call_id]
            editor_tabs = self.app.query_one("#editor-tabs", EditorTabs)
            editor_tabs.open_file(path)

    async def save_current_history(self) -> None:
        """Save the current session history."""
        if not self._coding_agent:
            return

        config = {"configurable": {"thread_id": "thread_1"}}
        try:
            state = await self._coding_agent.aget_state(config)
            if state and hasattr(state, "values"):
                messages = state.values.get("messages", [])
                if messages:
                    self.history_manager.save_session(
                        messages, self._session_id, project_root=project.root_dir
                    )
        except Exception:
            pass

    def _format_tool_call_preview(
        self, tool_name: str, tool_args: dict[str, Any]
    ) -> str | None:
        """Format a tool call for the terminal view."""
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

    def _extract_code(self, text: str) -> str:
        """Extract code from a markdown block."""
        match = re.search(r"```(.*)```", text, re.DOTALL)
        if match:
            return match.group(1)
        return text

    async def _save_conversation_to_memory(self) -> None:
        """Save the current conversation to long-term memory."""
        if (
            self._memory_service
            and self._memory_service.is_enabled
            and self._current_user_message
            and self._current_ai_message
        ):
            try:
                await self._memory_service.add_messages(
                    [self._current_user_message, self._current_ai_message],
                    metadata={
                        'session_id': self._session_id,
                        'project_root': project.root_dir,
                    },
                )
            except Exception:
                # Memory save errors should not affect the conversation
                pass

    def _on_tools_updated(self, new_tools: list[Any]) -> None:
        """当 MCP 工具更新时的回调处理。"""
        # 更新工具列表
        self._mcp_tools = new_tools

        # 重新创建智能体以应用新工具
        if self._coding_agent:
            self._coding_agent = create_coding_agent(
                plugin_tools=self._mcp_tools,
                checkpointer=self._checkpointer,
                memory_service=self._memory_service,
            )

        # 在终端显示更新信息
        terminal_view = self.app.query_one("#terminal-view", TerminalView)
        tool_count = len(new_tools)
        terminal_view.write(
            f"\n$ [MCP tools reloaded: {tool_count} tool"
            f"{' is' if tool_count == 1 else 's are'} available]\n",
            True,
        )

    async def start_config_watch(self) -> None:
        """启动配置文件监听器。"""
        if not self._config_watch_enabled:
            self._config_watch_enabled = True
            await self._mcp_manager.start_watching()

    async def stop_config_watch(self) -> None:
        """停止配置文件监听器。"""
        self._config_watch_enabled = False
        await self._mcp_manager.stop_watching()

    async def reload_mcp_tools(self) -> None:
        """手动重新加载 MCP 工具。"""
        terminal_view = self.app.query_one("#terminal-view", TerminalView)
        terminal_view.write("$ Reloading MCP tools...")
        try:
            await self._mcp_manager.reload_tools()
            terminal_view.write("- MCP tools reloaded successfully.\n", True)
        except Exception as e:
            terminal_view.write(f"- Error reloading MCP tools: {e}\n", True)

    def clear_session(self) -> None:
        """Reset the agent session."""
        self._checkpointer = MemorySaver()
        self._coding_agent = create_coding_agent(
            plugin_tools=self._mcp_tools,
            checkpointer=self._checkpointer,
            memory_service=self._memory_service,
        )
        self._terminal_tool_calls = []
        self._file_modification_tool_calls = {}
        self._session_id = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        self._current_user_message = None
        self._current_ai_message = None

    async def load_session(self, session_id: str, messages: list[AnyMessage]) -> None:
        """Load a previous session."""
        self._checkpointer = MemorySaver()
        self._coding_agent = create_coding_agent(
            plugin_tools=self._mcp_tools,
            checkpointer=self._checkpointer,
            memory_service=self._memory_service,
        )

        if self._coding_agent:
            config = {'configurable': {'thread_id': 'thread_1'}}
            await self._coding_agent.aupdate_state(config, {'messages': messages})

        self._terminal_tool_calls = []
        self._file_modification_tool_calls = {}
        self._session_id = session_id
        self._current_user_message = None
        self._current_ai_message = None
