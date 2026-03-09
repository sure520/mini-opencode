<div align="center">

# mini-OpenCode

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Code Style: Google](https://img.shields.io/badge/code%20style-google-3666d6.svg)](https://google.github.io/styleguide/pyguide.html)

[简体中文](./README.zh-CN.md)

**mini-OpenCode** is a lightweight, experimental AI Coding Agent inspired by [Deer-Code](https://github.com/MagicCube/deer-code) and [OpenCode](https://github.com/anomalyco/opencode). It demonstrates how Large Language Models (LLMs) can plan, reason, and iteratively write code with minimal infrastructure. Built on [LangGraph](https://github.com/langchain-ai/langgraph), it serves as a hackable foundation for understanding and building agentic coding systems.

<br/>
<img src="docs/images/tui_light_theme.png" width="45%" alt="Light Theme"/>
<img src="docs/images/tui_dark_theme.png" width="45%" alt="Dark Theme"/>
<br/>

</div>

---

## ✨ Features

- **🤖 Intelligent Coding Agent**: Leverages LangGraph for stateful, multi-step reasoning and execution.
- **📝 Context-Aware Task Management**: Built-in TODO system to track progress on complex, multi-step tasks.
- **🛠️ Comprehensive Toolset**: Includes tools for file operations (`read`, `write`, `edit`), filesystem navigation (`ls`, `tree`, `grep`), terminal commands (`bash`), web search (`tavily`), and web crawling (`firecrawl`).
- **🔌 Extensible Architecture**: Supports [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) for integrating external tools and servers.
- **🚀 Agent Skills System**: Dynamically loads specialized instructions, scripts, and resources (Skills) to improve performance on specific tasks (e.g., frontend design).
- **🎨 Interactive UI**: Features a clean terminal-based interface using [Textual](https://github.com/Textualize/textual), with support for automatic dark/light mode switching and streaming model responses.
- **⚡️ Slash Commands**: Quickly access features with commands like `/clear` to reset chat, `/resume` to restore sessions, and `/exit` to quit, complete with auto-suggestions.
- **⚙️ Highly Configurable**: flexible YAML-based configuration for models, tools, and API keys.
- **🔒 Type Safe**: Fully typed codebase (Python 3.12+) ensuring reliability and developer experience.
- **⚡ Performance Optimized**: Built-in file caching with LRU strategy and intelligent large file streaming processing.
- **📋 Code Templates**: Smart template system with code generators for rapid scaffolding (FastAPI CRUD, Python API, React components).
- **🧪 Testing Framework**: Integrated pytest with comprehensive unit tests for core modules.
- **📊 Structured Logging**: Advanced logging with structlog for better debugging and monitoring.

## 📖 Table of Contents

- [Features](#-features)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [Project Structure](#-project-structure)
- [Development](#-development)
- [Contributing](#-contributing)
- [Acknowledgments](#-acknowledgments)
- [License](#-license)

## 🚀 Prerequisites

- **Python 3.12** or higher
- **[uv](https://github.com/astral-sh/uv)** package manager (highly recommended for dependency management)
- API Keys for LLM (DeepSeek, Doubao) and optional web tools (Tavily, Firecrawl)

## 📦 Installation

1.  **Clone the repository**
    ```bash
    git clone https://github.com/your-username/mini-opencode.git
    cd mini-opencode
    ```

2.  **Install dependencies**
    ```bash
    uv sync
    # Or using make
    make install
    ```

## ⚙️ Configuration

1.  **Environment Variables**
    Copy the example environment file and fill in your API keys:
    ```bash
    cp .example.env .env
    ```
    Edit `.env`:
    ```ini
    DEEPSEEK_API_KEY=your_key_here
    # Optional:
    ARK_API_KEY=your_doubao_key
    KIMI_API_KEY=your_kimi_key
    TAVILY_API_KEY=your_tavily_key
    FIRECRAWL_API_KEY=your_firecrawl_key
    ```

2.  **Application Config**
    Copy the example configuration file:
    ```bash
    cp config.example.yaml config.yaml
    ```
    Edit `config.yaml` to customize enabled tools, model parameters, and MCP servers.

3.  **LangGraph Config (Optional)**
    If you plan to use LangGraph Studio to debug the agent, copy the example LangGraph configuration file:
    ```bash
    cp langgraph.example.json langgraph.json
    ```

## 💻 Usage

### CLI Mode
Run the agent directly on a project directory:
```bash
uv run -m mini_opencode /absolute/path/to/target/project
# Or using python
python -m mini_opencode /absolute/path/to/target/project
```

### Development Mode (LangGraph Studio)
Start the LangGraph development server to visualize and interact with the agent:
```bash
make dev
```
Then open [https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024](https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024) in your browser.

## 🏗️ Project Structure

```text
mini-opencode/
├── src/mini_opencode/
│   ├── agents/           # Core agent logic & state definitions
│   ├── cli/              # Terminal UI (Textual) components
│   ├── config/           # Configuration loading & validation
│   ├── models/           # LLM model factory & setup
│   ├── prompts/          # Prompt templates (Jinja2)
│   ├── skills/           # Skills system implementation (loader, parser, types)
│   ├── tools/            # Tool implementations
│   │   ├── file/         # File I/O (read, write, edit) with caching & streaming
│   │   ├── fs/           # File system (ls, tree, grep)
│   │   ├── terminal/     # Bash execution
│   │   ├── web/          # Search & Crawl
│   │   ├── mcp/          # MCP tools integration
│   │   ├── todo/         # Task management
│   │   └── template/     # Code template generators (FastAPI CRUD, etc.)
│   ├── cache/            # File and tool cache with LRU strategy
│   ├── logging_config.py # Structured logging configuration
│   ├── main.py           # CLI entry point
│   └── project.py        # Project context manager
├── skills/               # Agent Skills (instructions, scripts, and references)
├── tests/                # Unit tests (pytest)
│   └── unit/             # Unit tests for core modules
├── AGENTS.md             # Developer guide for agents
├── Makefile              # Build & run commands
├── config.example.yaml   # Template configuration
├── langgraph.example.json# Template LangGraph config
└── pyproject.toml        # Project dependencies & metadata
```

## 🔧 Development

### Adding New Tools
1.  Create a new file in `src/mini_opencode/tools/`.
2.  Use the `@tool` decorator with `parse_docstring=True`.
3.  Add Google-style docstrings for argument parsing.
4.  Register the tool in `src/mini_opencode/agents/coding_agent.py`.

### Code Style
- **Type Hints**: Mandatory for all functions.
- **Docstrings**: Google style required.
- **Naming**: `snake_case` for functions/vars, `PascalCase` for classes.

See [AGENTS.md](AGENTS.md) for detailed development guidelines.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (follow [Semantic Commits](https://www.conventionalcommits.org/), e.g., `git commit -m 'feat: Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

## 🙏 Acknowledgments

Special thanks to the developers of the following projects for their inspiration and architectural references:

- **[Deer-Code](https://github.com/MagicCube/deer-code)**
- **[OpenCode](https://github.com/anomalyco/opencode)**

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---
*Built with ❤️ using [LangGraph](https://langchain-ai.github.io/langgraph/) and [Textual](https://textual.textualize.io/).*
