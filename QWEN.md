# mini-OpenCode 项目指南

## 项目概述

**mini-OpenCode** 是一个轻量级的实验性 AI 编程代理，灵感来自 Deer-Code 和 OpenCode。它展示了大型语言模型（LLM）如何进行规划、推理和迭代编写代码。项目基于 **LangGraph** 构建，提供了一个简洁、可 hack 的基础架构，用于理解和构建代理式编程系统。

### 核心技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.12+ |
| 核心框架 | LangGraph |
| 记忆层 | Mem0 |
| CLI 界面 | Textual |
| 包管理 | uv |
| 测试 | pytest + pytest-asyncio + pytest-cov |
| 代码质量 | mypy, ruff |

## 快速开始

### 安装依赖

```bash
uv sync
# 或使用 make
make install
```

### 配置

1. 复制环境变量文件：
   ```bash
   cp .example.env .env
   ```
   编辑 `.env` 填入 API Key（DeepSeek、Ark/Doubao、Kimi、Tavily、Firecrawl、OpenAI for Mem0）

2. 复制配置文件：
   ```bash
   cp config.example.yaml config.yaml
   ```

### 运行

```bash
# CLI 模式
python -m mini_opencode /absolute/path/to/target/project

# 开发模式（LangGraph Studio）
make dev
```

## 项目结构

```
mini-opencode/
├── src/mini_opencode/
│   ├── agents/           # 核心代理逻辑与状态定义
│   ├── cli/              # 终端 UI (Textual) 组件
│   ├── config/           # 配置加载与验证
│   ├── models/           # LLM 模型工厂
│   ├── prompts/          # Prompt 模板 (Jinja2)
│   ├── skills/           # 技能系统实现
│   ├── tools/            # 工具实现
│   │   ├── file/         # 文件 I/O (read, write, edit)
│   │   ├── fs/           # 文件系统 (ls, tree, grep)
│   │   ├── terminal/     # Bash 执行
│   │   ├── web/          # 搜索与爬虫
│   │   ├── mcp/          # MCP 工具集成
│   │   ├── todo/         # 任务管理
│   │   └── template/     # 代码模板生成器
│   ├── cache/            # 文件缓存 (LRU)
│   ├── logging_config.py # 结构化日志配置
│   ├── main.py           # CLI 入口
│   ├── project.py        # 项目上下文管理
│   └── services/         # 业务服务 (agent, memory, session, message, tool)
├── skills/               # 代理技能目录
├── tests/                # 单元测试
├── Makefile              # 构建命令
├── pyproject.toml        # 项目依赖
└── config.example.yaml   # 配置模板
```

## 开发规范

### 代码风格

- **类型提示**：所有函数参数和返回值必须使用类型提示
- **文档字符串**：必须使用 Google 风格
- **命名规范**：
  - 文件/函数/变量：`snake_case`
  - 类名：`PascalCase`
  - 常量：`UPPER_SNAKE_CASE`
- **导入顺序**：标准库 → 第三方库 → 本地 `mini_opencode` 模块

### 添加新工具

1. 在 `src/mini_opencode/tools/` 创建新文件
2. 使用 `@tool` 装饰器，`parse_docstring=True`
3. 添加 Google 风格文档字符串
4. 在 `src/mini_opencode/agents/coding_agent.py` 注册工具

### 测试

```bash
# 运行所有测试
pytest

# 带覆盖率
pytest --cov=src/mini_opencode
```

### 代码检查

```bash
# 类型检查
mypy src/mini_opencode

# 代码格式检查
ruff check src/mini_opencode
```

## 配置说明

### config.yaml

- **models**: 选择 LLM 提供商（DeepSeek、Doubao、Kimi）
- **memory**: Mem0 记忆层配置（启用/禁用、用户ID、搜索限制、向量存储）
- **tools**: 启用/禁用工具，配置 API Key
- **mcp_servers**: MCP 服务器配置

### .env

- `DEEPSEEK_API_KEY`: DeepSeek API
- `ARK_API_KEY`: 字节跳动 Doubao API
- `KIMI_API_KEY`: 月之暗面 Kimi API
- `TAVILY_API_KEY`: Tavily 搜索 API
- `FIRECRAWL_API_KEY`: Firecrawl 爬虫 API
- `OPENAI_API_KEY`: OpenAI API（Mem0 记忆层使用）

## 可用工具

| 工具 | 功能 |
|------|------|
| read | 读取文件内容 |
| write | 写入文件 |
| edit | 编辑文件 |
| grep | 搜索文件内容 |
| ls | 列出目录 |
| tree | 显示目录树 |
| bash | 执行终端命令 |
| web_search | 网络搜索 |
| web_crawl | 网页爬取 |

## 记忆层 (Mem0)

mini-OpenCode 集成了 Mem0 记忆层，提供长期记忆功能：

### 特性

- **自动记忆保存**: 每次对话后自动保存到 Mem0
- **智能上下文注入**: 在系统提示词中自动注入相关记忆
- **用户隔离**: 支持多用户，通过 `user_id` 隔离记忆
- **可配置**: 通过 `config.yaml` 完全控制记忆功能

### 配置示例

```yaml
memory:
  enabled: true
  user_id: default_user
  search_limit: 5
  # 可选：自定义 Mem0 配置
  # config:
  #   vector_store:
  #     provider: qdrant
  #     config:
  #       path: ./.mem0/qdrant
```

### 环境变量

```bash
# Mem0 默认使用 OpenAI 进行嵌入和事实提取
OPENAI_API_KEY=sk-your-key
```

## 常用命令

```bash
# 安装依赖
make install

# 构建包
make build

# 开发模式（LangGraph Studio）
make dev

# 运行测试
pytest

# 类型检查
mypy src/mini_opencode

# 代码格式化
ruff check --fix src/mini_opencode
```