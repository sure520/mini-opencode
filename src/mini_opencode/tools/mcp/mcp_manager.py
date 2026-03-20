"""MCP 工具管理器 - 支持动态加载和热更新 MCP 工具。"""

import asyncio
from pathlib import Path
from typing import Any, Callable

from langchain.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from mini_opencode.config import get_config_section, load_config


class MCPToolManager:
    """管理 MCP 工具的生命周期，支持动态加载和热更新。"""

    def __init__(self):
        """初始化 MCP 工具管理器。"""
        self._tools: list[BaseTool] = []
        self._client: MultiServerMCPClient | None = None
        self._config_path: Path | None = None
        self._watch_task: asyncio.Task | None = None
        self._last_modified: float = 0
        self._callbacks: list[Callable[[list[BaseTool]], None]] = []
        self._running: bool = False

    @property
    def tools(self) -> list[BaseTool]:
        """获取当前加载的 MCP 工具列表。"""
        return self._tools

    async def load_tools(self) -> list[BaseTool]:
        """从配置文件加载 MCP 工具。"""
        servers = get_config_section(["tools", "mcp_servers"])
        if not servers:
            self._tools = []
            return self._tools

        try:
            client = MultiServerMCPClient(servers)
            self._tools = await client.get_tools()
            self._client = client
        except Exception as e:
            raise RuntimeError(f"Failed to load MCP tools: {e}") from e

        return self._tools

    async def reload_tools(self) -> list[BaseTool]:
        """重新加载 MCP 工具（热更新）。"""
        old_tools = self._tools.copy()
        
        try:
            await self.load_tools()
            
            # 通知所有回调
            for callback in self._callbacks:
                callback(self._tools)
            
            return self._tools
        except Exception as e:
            # 如果重新加载失败，恢复旧工具
            self._tools = old_tools
            raise RuntimeError(f"Failed to reload MCP tools: {e}") from e

    def on_tools_updated(self, callback: Callable[[list[BaseTool]], None]) -> None:
        """注册工具更新回调函数。"""
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[list[BaseTool]], None]) -> None:
        """移除工具更新回调函数。"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    async def start_watching(self, config_path: str | Path | None = None) -> None:
        """启动配置文件监听器。"""
        if config_path is None:
            import os
            config_path = os.getenv("MINI_OPENCODE_CONFIG", "config.yaml")
        
        self._config_path = Path(config_path)
        self._running = True
        
        self._watch_task = asyncio.create_task(self._watch_config())

    async def stop_watching(self) -> None:
        """停止配置文件监听器。"""
        self._running = False
        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
            self._watch_task = None

    async def _watch_config(self) -> None:
        """监听配置文件变化并自动重新加载工具。"""
        if not self._config_path or not self._config_path.exists():
            return

        import time
        
        while self._running:
            try:
                current_mtime = self._config_path.stat().st_mtime
                
                if current_mtime > self._last_modified and self._last_modified != 0:
                    # 配置文件已修改，等待一小段时间确保写入完成
                    await asyncio.sleep(0.5)
                    
                    # 重新加载配置缓存
                    load_config()
                    
                    # 重新加载 MCP 工具
                    await self.reload_tools()
                
                self._last_modified = current_mtime
                
            except FileNotFoundError:
                # 配置文件被删除，清空工具
                self._tools = []
                for callback in self._callbacks:
                    callback(self._tools)
            except Exception as e:
                # 记录错误但不中断监听
                pass
            
            # 每秒检查一次
            await asyncio.sleep(1)

    async def __aenter__(self) -> "MCPToolManager":
        """异步上下文管理器入口。"""
        await self.load_tools()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口。"""
        await self.stop_watching()


# 全局 MCP 工具管理器实例
_global_manager: MCPToolManager | None = None


def get_mcp_manager() -> MCPToolManager:
    """获取全局 MCP 工具管理器实例。"""
    global _global_manager
    if _global_manager is None:
        _global_manager = MCPToolManager()
    return _global_manager


async def reload_mcp_tools() -> list[BaseTool]:
    """便捷函数：重新加载 MCP 工具。"""
    manager = get_mcp_manager()
    return await manager.reload_tools()
