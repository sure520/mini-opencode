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
from mini_opencode.agents.state import MultiAgentState
from mini_opencode.agents.types import CoordinationState, TaskStatus
from mini_opencode.agents.workflow import CodingWorkflowRunner, compile_coding_workflow
from mini_opencode.cli.components import (
    ChatView,
    EditorTabs,
    TerminalView,
    TodoListView,
    WorkflowView,
)
from mini_opencode.cli.history import HistoryManager
from mini_opencode.config import get_config_section
from mini_opencode.config.memory_config import (
    get_tiered_memory_config,
    get_tiered_memory_enabled,
)
from mini_opencode.services import MemoryService
from mini_opencode.services.memory.tiered_memory import TieredMemoryManager
from mini_opencode.tools.mcp.mcp_manager import get_mcp_manager
from mini_opencode.tools.sandbox.manager import SandboxManager, get_sandbox_manager


class AgentController:
    """Controller for managing the AI agent and its interactions.

    Supports two modes:
    - "single": Traditional single-agent mode using create_coding_agent + astream.
    - "workflow": Multi-agent DAG workflow (Plan-Code-Test-Fix) using
      CodingWorkflowRunner + astream(stream_mode=["updates"]).
    """

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

        # Memory: dual-track (flat MemoryService or TieredMemoryManager)
        self._memory_service: MemoryService | None = None
        self._tiered_memory: TieredMemoryManager | None = None

        # Sandbox
        self._sandbox_manager: SandboxManager | None = None

        # Workflow mode
        self._mode: str = "single"  # "single" | "workflow"
        self._workflow_runner: CodingWorkflowRunner | None = None

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
        """Initialize the agent, memory, sandbox, and workflow mode."""
        terminal_view = self.app.query_one("#terminal-view", TerminalView)

        # --- Load MCP tools ---
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

        self._mcp_manager.on_tools_updated(self._on_tools_updated)

        if enable_config_watch:
            await self.start_config_watch()

        # --- Initialize memory (tiered or flat) ---
        memory_enabled = get_config_section(['memory', 'enabled'])
        memory_enabled = memory_enabled if isinstance(memory_enabled, bool) else True
        memory_user_id = get_config_section(['memory', 'user_id'])
        memory_user_id = (
            memory_user_id if isinstance(memory_user_id, str) else 'default'
        )

        tiered_enabled = get_tiered_memory_enabled()
        if tiered_enabled and memory_enabled:
            try:
                tiered_config = get_tiered_memory_config()
                self._tiered_memory = TieredMemoryManager(
                    config=tiered_config,
                    user_id=memory_user_id,
                    mem0_enabled=memory_enabled,
                )
                self._tiered_memory.short_term.set_session(self._session_id)
                st_cap = tiered_config.short_term_capacity
                wm_cap = tiered_config.working_memory_capacity
                lt_status = "Mem0" if self._tiered_memory.is_mem0_enabled else "off"
                terminal_view.write(
                    f"- Tiered memory enabled "
                    f"(ST:{st_cap}/WM:{wm_cap}/LT:{lt_status})\n",
                    True,
                )
            except Exception as e:
                terminal_view.write(
                    f"- Tiered memory init failed ({e}), falling back to flat.\n",
                    True,
                )
                self._tiered_memory = None

        # Fallback to flat MemoryService if tiered is not active
        if self._tiered_memory is None:
            self._memory_service = MemoryService(
                enabled=memory_enabled, user_id=memory_user_id
            )
            if self._memory_service.is_enabled:
                terminal_view.write(
                    f"- Memory service (flat) enabled for user: {memory_user_id}\n",
                    True,
                )
            else:
                terminal_view.write("- Memory service disabled.\n", True)

        # --- Initialize sandbox ---
        sandbox_enabled = get_config_section(['sandbox', 'enabled'])
        sandbox_enabled = sandbox_enabled if isinstance(sandbox_enabled, bool) else False
        if sandbox_enabled:
            try:
                self._sandbox_manager = get_sandbox_manager(
                    project_root=str(project.root_dir)
                )
                stats = self._sandbox_manager.get_stats()
                terminal_view.write(
                    f"- Sandbox: enabled ({stats['provider']}, "
                    f"network={stats['network_mode']})\n",
                    True,
                )
            except Exception as e:
                terminal_view.write(f"- Sandbox init failed: {e}\n", True)
                self._sandbox_manager = None
        else:
            terminal_view.write("- Sandbox: disabled\n", True)

        # --- Initialize workflow mode ---
        workflow_enabled = get_config_section(['workflow', 'enabled'])
        workflow_enabled = (
            workflow_enabled if isinstance(workflow_enabled, bool) else False
        )
        if workflow_enabled:
            default_mode = get_config_section(['workflow', 'default_mode'])
            self._mode = (
                default_mode
                if isinstance(default_mode, str) and default_mode in ("single", "workflow")
                else "single"
            )
            max_iter = get_config_section(['workflow', 'max_fix_iterations'])
            max_iter = max_iter if isinstance(max_iter, int) else 3
            self._workflow_runner = CodingWorkflowRunner(max_iterations=max_iter)

        if self._mode == "workflow":
            terminal_view.write(
                "- Agent mode: workflow (Plan-Code-Test-Fix)\n", True
            )
        else:
            terminal_view.write("- Agent mode: single\n", True)

        # --- Load single-agent (always needed for single mode and session resume) ---
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
            terminal_view.write(f"- Error loading agent: {e}\n", True)
            await asyncio.sleep(3)
            self.app.exit(1)

    # ==================== User Input Handling ====================

    async def handle_user_input(self, user_message: HumanMessage) -> None:
        """Handle user input - dispatches to single-agent or workflow mode."""
        self._cancelled = False
        self._current_user_message = user_message
        self._current_ai_message = None
        self.process_outgoing_message(user_message)
        self.is_generating = True

        # Add to tiered short-term memory
        if self._tiered_memory:
            self._tiered_memory.add_message(
                user_message.content,
                metadata={'role': 'human', 'session_id': self._session_id},
            )

        await asyncio.sleep(0)

        try:
            if self._mode == "workflow" and self._workflow_runner:
                await self._handle_workflow_input(user_message)
            else:
                await self._handle_single_agent_input(user_message)
        except asyncio.CancelledError:
            self._cancelled = True
            terminal_view = self.app.query_one("#terminal-view", TerminalView)
            terminal_view.write("\n$ [Operation cancelled]")
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
                await self._save_conversation_to_memory()
            if hasattr(self.app, 'focus_input'):
                self.app.focus_input()

    async def _handle_single_agent_input(self, user_message: HumanMessage) -> None:
        """Handle input in single-agent mode (existing astream logic)."""
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
                if self._cancelled:
                    break

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

    async def _handle_workflow_input(self, user_message: HumanMessage) -> None:
        """Handle input in workflow mode (Plan-Code-Test-Fix DAG)."""
        terminal_view = self.app.query_one("#terminal-view", TerminalView)
        workflow_view = self.app.query_one("#workflow-view", WorkflowView)
        bottom_tabs = self.app.query_one("#bottom-right-tabs", TabbedContent)

        # Switch to workflow tab
        bottom_tabs.active = "workflow-tab"

        # Get memory context
        memory_context = await self._get_memory_context_async(user_message.content)

        # Add task context to working memory
        if self._tiered_memory:
            self._tiered_memory.add_task_context(
                task_id=self._session_id,
                content=user_message.content,
                metadata={'type': 'workflow_request'},
            )

        # Build initial state
        memory_user_id = get_config_section(['memory', 'user_id'])
        memory_user_id = (
            memory_user_id if isinstance(memory_user_id, str) else 'default'
        )
        max_iter = get_config_section(['workflow', 'max_fix_iterations'])
        max_iter = max_iter if isinstance(max_iter, int) else 3

        initial_state = MultiAgentState.create_initial(
            user_id=memory_user_id,
            memory_context=memory_context,
        )
        initial_state["messages"] = [user_message]
        initial_state["coordination"] = CoordinationState(
            max_iterations=max_iter
        )

        # Compile workflow and stream updates
        compiled = compile_coding_workflow()
        terminal_view.write("$ Workflow started (Plan-Code-Test-Fix)")

        final_state: dict[str, Any] | None = None

        try:
            async for chunk in compiled.astream(
                initial_state,
                stream_mode="updates",
                config={"recursion_limit": 50},
            ):
                if self._cancelled:
                    break

                await asyncio.sleep(0)

                for node_name, node_output in chunk.items():
                    if self._cancelled:
                        break

                    # Extract progress info from node output
                    subtasks = node_output.get("subtasks", [])
                    coordination = node_output.get(
                        "coordination", CoordinationState()
                    )

                    phase = (
                        coordination.phase.value
                        if hasattr(coordination, 'phase')
                        else node_name
                    )

                    # Update workflow view
                    subtask_dicts = []
                    for t in subtasks:
                        if hasattr(t, 'to_dict'):
                            subtask_dicts.append(t.to_dict())
                        elif isinstance(t, dict):
                            subtask_dicts.append(t)

                    workflow_view.update_status(
                        phase=phase,
                        subtasks=subtask_dicts,
                        iteration=coordination.iteration_count
                        if hasattr(coordination, 'iteration_count')
                        else 0,
                        max_iterations=coordination.max_iterations
                        if hasattr(coordination, 'max_iterations')
                        else max_iter,
                    )

                    terminal_view.write(
                        f"  [{node_name}] phase: {phase}", muted=True
                    )

                    final_state = node_output

        except asyncio.CancelledError:
            self._cancelled = True
            terminal_view.write("\n$ [Workflow cancelled]")
            workflow_view.clear_workflow()
            return

        # Extract and display result
        if final_state and not self._cancelled:
            runner = CodingWorkflowRunner()
            result_text = runner.get_result(final_state)
            summary = runner.get_summary(final_state)

            ai_response = AIMessage(content=result_text)
            self.process_incoming_message(ai_response)
            self._current_ai_message = ai_response

            terminal_view.write(
                f"\n$ Workflow complete: "
                f"{summary['completed_tasks']}/{summary['total_tasks']} tasks, "
                f"{summary['fix_iterations']} fix iterations"
            )
        elif not self._cancelled:
            fallback = AIMessage(
                content="Workflow completed but no final response was generated."
            )
            self.process_incoming_message(fallback)
            self._current_ai_message = fallback

    # ==================== Mode Management ====================

    def toggle_mode(self) -> str:
        """Toggle between single-agent and workflow mode.

        Returns:
            The new mode name, or an error message.
        """
        if self.is_generating:
            return "Cannot switch mode while agent is running."

        workflow_enabled = get_config_section(['workflow', 'enabled'])
        if not (isinstance(workflow_enabled, bool) and workflow_enabled):
            return "Workflow mode is not enabled in config. Set workflow.enabled: true."

        if self._mode == "single":
            self._mode = "workflow"
        else:
            self._mode = "single"

        return self._mode

    # ==================== Message Display ====================

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

    # ==================== Tool Call Handling ====================

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

    # ==================== History & Memory ====================

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

    async def _save_conversation_to_memory(self) -> None:
        """Save the current conversation to memory."""
        if not self._current_user_message or not self._current_ai_message:
            return

        # Tiered memory path
        if self._tiered_memory:
            try:
                ai_content = (
                    self._current_ai_message.content
                    if isinstance(self._current_ai_message.content, str)
                    else str(self._current_ai_message.content)
                )
                self._tiered_memory.add_message(
                    ai_content,
                    metadata={'role': 'assistant', 'session_id': self._session_id},
                )
                # Also persist to long-term memory
                combined = (
                    f"User: {self._current_user_message.content}\n"
                    f"Assistant: {ai_content}"
                )
                await self._tiered_memory.add_to_long_term(
                    content=combined,
                    metadata={
                        'session_id': self._session_id,
                        'project_root': str(project.root_dir),
                    },
                )
            except Exception:
                pass
            return

        # Flat MemoryService fallback
        if self._memory_service and self._memory_service.is_enabled:
            try:
                await self._memory_service.add_messages(
                    [self._current_user_message, self._current_ai_message],
                    metadata={
                        'session_id': self._session_id,
                        'project_root': project.root_dir,
                    },
                )
            except Exception:
                pass

    async def _get_memory_context_async(self, query: str) -> str:
        """Get memory context string for prompt injection.

        Args:
            query: The user query to search memory for.

        Returns:
            Formatted memory context string.
        """
        if self._tiered_memory:
            context = self._tiered_memory.get_memory_context(query)
            try:
                long_term_results = await self._tiered_memory.search_long_term(
                    query, limit=3
                )
                if long_term_results:
                    lt_texts = [
                        f"- {r.memory.content[:200]}" for r in long_term_results
                    ]
                    context += "\n\n## Long-term Memory:\n" + "\n".join(lt_texts)
            except Exception:
                pass
            return context

        if self._memory_service and self._memory_service.is_enabled:
            try:
                return await self._memory_service.get_memory_context(query)
            except Exception:
                pass

        return ""

    # ==================== Formatting Helpers ====================

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

    # ==================== MCP & Config Watch ====================

    def _on_tools_updated(self, new_tools: list[Any]) -> None:
        """Callback when MCP tools are updated."""
        self._mcp_tools = new_tools

        if self._coding_agent:
            self._coding_agent = create_coding_agent(
                plugin_tools=self._mcp_tools,
                checkpointer=self._checkpointer,
                memory_service=self._memory_service,
            )

        terminal_view = self.app.query_one("#terminal-view", TerminalView)
        tool_count = len(new_tools)
        terminal_view.write(
            f"\n$ [MCP tools reloaded: {tool_count} tool"
            f"{' is' if tool_count == 1 else 's are'} available]\n",
            True,
        )

    async def start_config_watch(self) -> None:
        """Start config file watcher."""
        if not self._config_watch_enabled:
            self._config_watch_enabled = True
            await self._mcp_manager.start_watching()

    async def stop_config_watch(self) -> None:
        """Stop config file watcher."""
        self._config_watch_enabled = False
        await self._mcp_manager.stop_watching()

    async def reload_mcp_tools(self) -> None:
        """Manually reload MCP tools."""
        terminal_view = self.app.query_one("#terminal-view", TerminalView)
        terminal_view.write("$ Reloading MCP tools...")
        try:
            await self._mcp_manager.reload_tools()
            terminal_view.write("- MCP tools reloaded successfully.\n", True)
        except Exception as e:
            terminal_view.write(f"- Error reloading MCP tools: {e}\n", True)

    # ==================== Session Management ====================

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

        # Clear tiered memory session
        if self._tiered_memory:
            self._tiered_memory.clear_session()
            self._tiered_memory.short_term.set_session(self._session_id)

        # Clear workflow view
        try:
            workflow_view = self.app.query_one("#workflow-view", WorkflowView)
            workflow_view.clear_workflow()
        except Exception:
            pass

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

        # Update tiered memory session
        if self._tiered_memory:
            self._tiered_memory.short_term.set_session(session_id)

    async def cleanup_sandbox(self) -> None:
        """Clean up sandbox resources."""
        if self._sandbox_manager:
            try:
                await self._sandbox_manager.cleanup()
            except Exception:
                pass
