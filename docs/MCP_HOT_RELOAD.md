# MCP 配置热重载功能

## 功能概述

MCP 配置热重载功能允许在 mini-OpenCode 运行时动态修改 MCP 服务器配置，无需重启应用程序即可加载新的 MCP 工具。

## 实现原理

### 核心组件

1. **MCPToolManager** (`src/mini_opencode/tools/mcp/mcp_manager.py`)
   - 管理 MCP 工具的生命周期
   - 支持动态加载和重新加载工具
   - 提供配置文件监听功能

2. **配置文件监听器**
   - 监控 `config.yaml` 文件的变化
   - 检测到修改后自动触发工具重新加载
   - 每秒检查一次文件修改时间

3. **工具更新回调机制**
   - 当工具列表更新时，自动重新创建智能体
   - 确保智能体始终使用最新的工具列表

## 使用方式

### 1. 自动热重载（默认启用）

启动应用程序后，系统会自动监听配置文件的变化：

```bash
python -m mini_opencode /path/to/project
```

当你在 `config.yaml` 中添加、修改或删除 MCP 服务器配置时，系统会自动：
1. 检测到配置文件变化
2. 重新加载 MCP 工具
3. 更新智能体的工具列表
4. 在终端显示更新信息

### 2. 手动重新加载

使用 `/mcp-reload` 命令手动触发 MCP 工具重新加载：

```
/mcp-reload
```

这会在不修改配置文件的情况下，强制重新加载当前的 MCP 配置。

## 配置示例

### 添加新的 MCP 服务器

在 `config.yaml` 中添加：

```yaml
tools:
  mcp_servers:
    docs-langchain:
      transport: 'streamable_http'
      url: 'https://docs.langchain.com/mcp'
    your-new-server:
      transport: 'stdio'
      command: 'npx'
      args:
        - '@modelcontextprotocol/server-example'
```

保存文件后，系统会自动加载新的 MCP 服务器。

### 修改现有配置

直接编辑 `config.yaml` 中的 MCP 服务器配置，保存后会自动应用新配置。

### 删除服务器

从 `config.yaml` 中移除服务器配置，保存后该服务器的工具会被移除。

## 技术细节

### 配置文件监听

```python
# 启动监听
await mcp_manager.start_watching(config_path)

# 停止监听
await mcp_manager.stop_watching()
```

### 工具重新加载

```python
# 重新加载工具
tools = await mcp_manager.reload_tools()

# 获取当前工具列表
current_tools = mcp_manager.tools
```

### 注册更新回调

```python
def on_tools_updated(new_tools):
    print(f"Tools updated: {len(new_tools)} tools available")

mcp_manager.on_tools_updated(on_tools_updated)
```

## 注意事项

1. **文件写入延迟**: 配置文件保存后，系统会等待 0.5 秒以确保文件完全写入
2. **错误处理**: 如果重新加载失败，系统会保留之前的工具列表
3. **性能影响**: 配置文件监听器每秒检查一次，对性能影响极小
4. **应用退出**: 应用程序会自动清理监听器资源

## 禁用自动热重载

如果需要禁用自动配置文件监听（不推荐）：

```python
# 在 init_agent 时设置 enable_config_watch=False
await agent_controller.init_agent(enable_config_watch=False)
```

## 调试

查看终端输出中的 MCP 工具加载信息：

```
$ Loading MCP tools...
- 2 tools are loaded.
$ Loading agent...
- Agent loaded successfully.

$ [MCP tools reloaded: 3 tools are available]
```

## 架构优势

1. **实时性**: 无需重启应用即可使用新工具
2. **可靠性**: 加载失败时自动回滚到之前的状态
3. **灵活性**: 支持自动和手动两种模式
4. **资源效率**: 使用异步监听，资源占用极低
