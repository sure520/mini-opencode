from langchain_mcp_adapters.client import MultiServerMCPClient

from mini_opencode.config import get_config_section


async def load_mcp_tools():
    """Load MCP tools from the config."""
    servers = get_config_section(["tools", "mcp_servers"])
    if not servers:
        return []
    client = MultiServerMCPClient(servers)
    return await client.get_tools()
