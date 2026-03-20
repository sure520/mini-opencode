# Architecture Overview: mini-OpenCode

This document provides a high-level overview of the mini-OpenCode architecture, development practices, and project structure to assist developers and AI agents in understanding and contributing to the codebase.

## 1. Project Overview
mini-OpenCode is a lightweight, experimental AI Coding Agent inspired by Deer-Code and OpenCode. It leverages **LangGraph** to implement a stateful, iterative reasoning loop for code development.

### Core Architecture
- **State Management**: Uses `CodingAgentState` (extending LangGraph's `MessagesState`) to track conversation history and a persistent list of `todos`.
- **Agent Logic**: The core agent is defined in `src/mini_opencode/agents/coding_agent.py`, using `create_agent` from LangGraph.
- **UI Layer**: A terminal-based interface built with **Textual** (`src/mini_opencode/cli/`), providing streaming responses and interactive components.
- **Tooling System**: A modular toolset in `src/mini_opencode/tools/` covering file I/O, filesystem navigation, shell execution, and web research.
- **Skills System**: A dynamic system (`src/mini_opencode/skills/`) that loads specialized instructions and resources from the `skills/` directory to enhance agent capabilities.

### UI Components
The UI layer includes several key components:
- **TerminalView**: Displays terminal output with mouse selection support (click and drag to select content)
- **ResizeGrip**: A draggable handle for resizing the terminal area vertically (hover to show, drag to resize)
- **ChatView**: Chat interface for interacting with the AI agent
- **EditorTabs**: Tab-based code editor
- **TodoListView**: Task management view

### Task Cancellation Architecture
The application implements a robust task cancellation mechanism:

- **Cancellation Flag**: `AgentController._cancelled` flag is checked at multiple points during agent execution
- **Worker Management**: Textual `Worker` objects are used to run agent tasks asynchronously, with proper cancellation handling
- **State Propagation**: `is_generating` state flows through: `App` → `ChatView` → `ChatInput` → Button UI
- **Immediate Response**: `asyncio.sleep(0)` is used in tight loops to allow immediate cancellation detection
- **Graceful Shutdown**: All message processing methods check the cancellation flag and return early when cancelled

## 2. Build & Commands
The project uses **uv** as its primary package manager.

### Development Commands
- **Install Dependencies**: `uv sync` or `make install`
- **Build Package**: `uv build`
- **Run CLI**: `python -m mini_opencode <target_directory>`
- **Run Dev Server**: `make dev` (starts LangGraph development server for visualization and debugging)

## 3. Code Style
mini-OpenCode follows strict Python coding standards to ensure reliability and maintainability.

### Conventions
- **Version**: Python 3.12+ required.
- **Type Hints**: Mandatory for all function parameters and return values. Use modern syntax like `T | None` and `list[T]`.
- **Naming**:
  - Files/Functions/Variables: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_SNAKE_CASE`
- **Formatting**: Google-style docstrings are required for all public modules, classes, and functions.
- **Imports**: Organized as: (1) Standard library, (2) Third-party, (3) Local `mini_opencode` modules.

## 4. Testing
- **Framework**: pytest is configured with pytest-asyncio and pytest-cov for comprehensive testing.
- **Coverage**: Core modules have complete unit tests, including text editor and cache modules.
- **Validation**: Developers can run tests with `pytest` and use LangGraph Studio (`make dev`) for tracing and debugging agent logic.

## 5. Security
- **Credential Management**: API keys and sensitive tokens must be stored in a `.env` file or environment variables, never hardcoded.
- **Path Safety**: Tools (like `read`, `write`, `edit`) strictly validate that paths are absolute to prevent accidental operations outside the intended project context.
- **Tool Execution**: The `bash` tool executes shell commands; agents should exercise caution and avoid destructive operations unless explicitly requested.

## 6. Configuration
- **Application Config**: Managed via `config.yaml` (see `config.example.yaml` for a template). This file controls model selection (DeepSeek, Doubao, Kimi), tool activation, and MCP server integrations.
- **Environment**: `.env` file handles API keys for LLM providers and web tools (Tavily, Firecrawl).
- **Agent State**: Persistent state is managed through LangGraph checkpointers, allowing session resumption.
