import json
import subprocess
import os
from typing import List, Dict, Any


class MCPClient:
    """Client for communicating with MCP servers via stdio"""
    
    def __init__(self, server_command: str, server_args: List[str], env: Dict[str, str] = None):
        self.server_command = server_command
        self.server_args = server_args
        self.env = env or {}
        self.process = None
        self.tools = []
        
    def start(self):
        """Start the MCP server process"""
        # Prepare environment variables
        server_env = os.environ.copy()
        server_env.update(self.env)
        
        # On Windows, we need to use shell=True or add .cmd extension
        import platform
        is_windows = platform.system() == "Windows"
        
        # Build command
        if is_windows and self.server_command == "npx":
            # On Windows, use npx.cmd or shell=True
            command = [self.server_command] + self.server_args
            shell = True
        else:
            command = [self.server_command] + self.server_args
            shell = False
        
        # Start the server process
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=server_env,
            text=True,
            bufsize=1,
            shell=shell,
            encoding='utf-8',
            errors='replace'  # Replace invalid characters instead of crashing
        )
        
        print(f"✓ Started MCP server: {self.server_command} {' '.join(self.server_args)}")
        
        # Initialize connection
        self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "eve-llm-host",
                "version": "1.0.0"
            }
        })
        
        # List available tools
        self._list_tools()
        
    def _send_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send a JSON-RPC request to the MCP server"""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {}
        }
        
        request_json = json.dumps(request) + "\n"
        self.process.stdin.write(request_json)
        self.process.stdin.flush()
        
        # Read response with timeout
        import select
        import sys
        
        # Check if data is available (with timeout)
        if sys.platform == "win32":
            # Windows doesn't support select on pipes, so just try to read
            try:
                response_line = self.process.stdout.readline()
                if response_line:
                    return json.loads(response_line)
            except Exception as e:
                print(f"   ⚠️  Error reading response: {e}")
                return {}
        else:
            # Unix-like systems can use select
            import select
            ready, _, _ = select.select([self.process.stdout], [], [], 10)  # 10 second timeout
            if ready:
                response_line = self.process.stdout.readline()
                if response_line:
                    return json.loads(response_line)
        
        return {}
    
    def _list_tools(self):
        """Discover available tools from the MCP server"""
        response = self._send_request("tools/list")
        
        if "result" in response and "tools" in response["result"]:
            self.tools = response["result"]["tools"]
            print(f"✓ Discovered {len(self.tools)} tools from MCP server")
            for tool in self.tools:
                print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
        else:
            print("⚠️  No tools found or error listing tools")
            
    def get_tools_for_llm(self) -> List[Dict[str, Any]]:
        """Convert MCP tools to OpenAI function calling format.
        
        Note: tenant_id is filtered out from tool schemas because it's automatically
        injected at runtime by llm_host.py from the authenticated user's token.
        This prevents the LLM from asking users for tenant_id.
        """
        # Parameters that should be hidden from LLM (injected at runtime)
        HIDDEN_PARAMS = {"tenant_id"}
        
        llm_tools = []
        
        for tool in self.tools:
            # Get the input schema
            input_schema = tool.get("inputSchema", {
                "type": "object",
                "properties": {},
                "required": []
            })
            
            # Filter out hidden parameters from properties
            filtered_properties = {
                k: v for k, v in input_schema.get("properties", {}).items()
                if k not in HIDDEN_PARAMS
            }
            
            # Filter out hidden parameters from required list
            filtered_required = [
                r for r in input_schema.get("required", [])
                if r not in HIDDEN_PARAMS
            ]
            
            # Build filtered schema
            filtered_schema = {
                "type": input_schema.get("type", "object"),
                "properties": filtered_properties,
            }
            if filtered_required:
                filtered_schema["required"] = filtered_required
            
            llm_tool = {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": filtered_schema
                }
            }
            llm_tools.append(llm_tool)
            
        return llm_tools
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool on the MCP server"""
        response = self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        
        if "result" in response:
            return response["result"]
        elif "error" in response:
            return {"error": response["error"]}
        else:
            return {"error": "Unknown error calling tool"}
    
    def stop(self):
        """Stop the MCP server process"""
        if self.process:
            self.process.terminate()
            self.process.wait()
            print("✓ MCP server stopped")
