import os
import sys
import json
import asyncio
import shutil
from typing import Dict, Any, List, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class MCPManager:
    def __init__(self, config_path: str = "mcp_config.json"):
        self.config_path = config_path
        self.config = {}
        self.servers: Dict[str, dict] = {} # server_name -> {"session": ClientSession, "tools": [], "read_stream": ..., "write_stream": ...}
        self.load_config()

    def load_config(self):
        if not os.path.exists(self.config_path):
            print(f"MCP config not found at {self.config_path}. No external servers will be loaded.")
            self.config = {"mcpServers": {}}
            return
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"Error loading MCP config: {e}")
            self.config = {"mcpServers": {}}

    async def initialize(self):
        mcp_servers = self.config.get("mcpServers", {})
        for server_name, server_config in mcp_servers.items():
            command = server_config.get("command")
            args = server_config.get("args", [])
            env = server_config.get("env", None)

            if not command:
                print(f"Server {server_name} missing 'command' in config.")
                continue

            # On Windows, subprocess.Popen without shell=True often fails to find commands like 'uvx' or 'npx' 
            # if the extension (.exe, .cmd) is omitted or it's not strictly in PATH.
            # Using shutil.which to resolve the absolute path and extension.
            resolved_command = shutil.which(command)
            if not resolved_command:
                # Fallback: maybe it's in the python Scripts folder?
                scripts_dir = os.path.join(sys.prefix, "Scripts")
                resolved_command = shutil.which(command, path=os.environ.get("PATH", "") + os.pathsep + scripts_dir)
            
            if resolved_command:
                command = resolved_command
            else:
                print(f"Server {server_name}: '{command}' was not found in PATH. Please ensure it's installed.")

            try:
                server_params = StdioServerParameters(
                    command=command,
                    args=args,
                    env=env
                )
                print(f"Connecting to MCP Server: {server_name} via {command} {' '.join(args)}...")
                
                # Using stdio_client as an async context manager
                # However, to keep it alive across requests, we'll manually enter the context
                # and store the streams and session
                import contextlib
                manager = stdio_client(server_params)
                read_stream, write_stream = await manager.__aenter__()
                
                session = ClientSession(read_stream, write_stream)
                await session.__aenter__()
                
                # Initialize the session
                await session.initialize()
                
                # Fetch available tools
                tools_response = await session.list_tools()
                
                self.servers[server_name] = {
                    "session": session,
                    "manager": manager,
                    "tools": tools_response.tools,
                    "name": server_name
                }
                print(f"✅ Connected to MCP Server '{server_name}'. Managed {len(tools_response.tools)} tools.")
                
            except Exception as e:
                print(f"❌ Failed to connect to MCP Server '{server_name}': {e}")

    async def get_all_tools(self) -> List[dict]:
        """
        Returns a list of tools structured for the LLM provider.
        We'll namespace tool names with the server name to avoid collisions: server_name__tool_name
        """
        all_tools = []
        for server_name, server_data in self.servers.items():
            for tool in server_data["tools"]:
                # tool is an instance of mcp.types.Tool
                namespaced_name = f"mcp_{server_name}___{tool.name}"
                
                # Schema conversion (MCP UI schema to Gemini/OpenAI expected schema structure is largely compatible as JSON Schema)
                tool_def = {
                    "type": "function",
                    "function": {
                        "name": namespaced_name,
                        "description": f"[MCP: {server_name}] {tool.description or tool.name}",
                        "parameters": tool.inputSchema
                    }
                }
                all_tools.append(tool_def)
        return all_tools

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict) -> Any:
        if server_name not in self.servers:
            return f"Error: MCP Server '{server_name}' is not running."
        
        session = self.servers[server_name]["session"]
        try:
            result = await session.call_tool(tool_name, arguments)
            # result is an CallToolResult which contains a list of content
            output = ""
            for content in result.content:
                if content.type == "text":
                    output += content.text + "\n"
                else:
                    output += f"[{content.type} content]"
            
            if result.isError:
                return f"MCP Tool Error: {output}"
            return output.strip() if output else "Task completed successfully."
        except Exception as e:
            return f"Error executing MCP tool '{tool_name}' on '{server_name}': {str(e)}"

    async def close(self):
        for server_name, server_data in self.servers.items():
            try:
                await server_data["session"].__aexit__(None, None, None)
                await server_data["manager"].__aexit__(None, None, None)
                print(f"Closed connection to MCP Server '{server_name}'.")
            except Exception as e:
                print(f"Error closing MCP Server '{server_name}': {e}")
        self.servers.clear()

# Singleton instance
mcp_manager = MCPManager()
