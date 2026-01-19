# mini-opencode

A lightweight experimental AI Coding Agent inspired by OpenCode. It explores how LLMs can plan, reason, and iteratively write code with minimal infrastructure, aiming to provide a simple, hackable foundation for understanding and building agentic coding systems.

## Project Structure

```
mini-opencode/
├── src/mini_opencode/
│   ├── agents/          # Agent implementations
│   │   ├── coding_agent.py    # Main coding agent
│   │   └── state.py           # Agent state management
│   ├── tools/           # Tool implementations
│   │   ├── file/        # File operations (read, write, edit)
│   │   ├── terminal/    # Bash/terminal commands
│   │   ├── web/         # Web search and crawl
│   │   ├── todo/        # Task management
│   │   └── mcp/         # MCP server integration
│   ├── cli/             # CLI and TUI components
│   ├── models/          # LLM model configurations
│   ├── prompts/         # Prompt templates
│   └── config/          # Configuration management
├── config.yaml          # Main configuration file
└── pyproject.toml       # Project dependencies
```

## Core Components

### Coding Agent
- Built with LangGraph for stateful, multi-step reasoning
- Supports tool use for file operations, terminal commands, web search
- Maintains conversation history and todo list in state
- Configurable through `config.yaml`

### Available Tools
- **File Operations**: `read`, `write`, `edit` - Read, create, and modify files
- **Terminal**: `bash` - Execute shell commands
- **Filesystem**: `ls`, `tree`, `grep` - Navigate and search codebase
- **Web**: `web_search`, `web_crawl` - Search and crawl websites
- **Task Management**: `todo_write` - Create and manage task lists
- **MCP**: Integration with MCP servers for extended capabilities

### Configuration
- `config.yaml` controls enabled tools, LLM settings, and MCP servers
- Supports DeepSeek, Doubao, and other LangChain-compatible models
- Environment variables for API keys (DEEPSEEK_API_KEY, FIRECRAWL_API_KEY, TAVILY_API_KEY)

## Development Commands

```bash
# Install dependencies
uv sync

# Run the CLI
python -m mini_opencode [project_root]
```

## Key Features

- **Minimal Infrastructure**: Simple, hackable codebase for understanding agentic systems
- **Tool Use**: Comprehensive tools for code manipulation and research
- **State Management**: Maintains conversation context and task lists
- **Configurable**: Easy to customize tools, models, and prompts
- **MCP Support**: Extensible through Model Context Protocol servers
- **Interactive CLI**: Terminal-based UI for conversations

## Environment Variables

- `DEEPSEEK_API_KEY` - DeepSeek API key
- `ARK_API_KEY` - Doubao/ARK API key
- `FIRECRAWL_API_KEY` - Firecrawl API key for web crawling
- `TAVILY_API_KEY` - Tavily API key for web search
- `PROJECT_ROOT` - Project root directory (default: current directory)
- `MINI_OPENCODE_CONFIG` - Path to config file (default: `config.yaml`)