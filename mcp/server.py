"""
MCP Server initialization
Registers all available MCP tool servers
"""
from mcp.vaulta import vaulta_mcp
from mcp.status_mcp import status_mcp


class MCPServer:
    """Unified MCP Server with all tool categories"""
    
    def __init__(self):
        self.servers = {
            'vaulta': vaulta_mcp,
            'status': status_mcp
        }
        self.tools = self._collect_tools()
    
    def _collect_tools(self):
        """Collect all tools from registered servers"""
        all_tools = []
        for server_name, server in self.servers.items():
            for tool in server.tools:
                tool['server'] = server_name
                all_tools.append(tool)
        return all_tools
    
    def call_tool(self, tool_name: str, arguments: dict):
        """Route tool call to appropriate server"""
        # Find which server handles this tool
        for server_name, server in self.servers.items():
            tool_names = [t['name'] for t in server.tools]
            if tool_name in tool_names:
                return server.call_tool(tool_name, arguments)
        
        return {'error': f'Tool {tool_name} not found in any server'}
    
    def get_tools_list(self):
        """Get list of all available tools"""
        return self.tools
    
    def get_tools_by_server(self, server_name: str):
        """Get tools for a specific server"""
        if server_name in self.servers:
            return self.servers[server_name].tools
        return []


# Global MCP server instance
mcp_server = MCPServer()
