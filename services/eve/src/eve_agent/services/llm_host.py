import json
import requests
from ..core.config import get_settings

settings = get_settings()
OPENAI_API_URL = f"{settings.openai_base_url}/chat/completions"


class LLMHost:
    def __init__(self, system_prompt=None, mcp_client=None):
        self.conversation_history = []
        self.tools = []
        self.mcp_client = mcp_client  # Primary client (for backward compatibility)
        self.mcp_clients = []  # List of all MCP clients
        
        # Add system prompt if provided
        if system_prompt:
            self.conversation_history.append({
                "role": "system",
                "content": system_prompt
            })
        
    def add_mcp_tools(self, tools):
        """Add MCP tools to the LLM's available tools"""
        self.tools = tools
        print(f"✓ Loaded {len(tools)} MCP tools")
        
    def call_llm(self, user_message, tools=None):
        """Call OpenAI API for chat completions"""
        # Add user message to history (only if not empty)
        if user_message:
            self.conversation_history.append({
                "role": "user",
                "content": user_message
            })
        
        # Prepare request payload
        payload = {
            "model": settings.llm_model,
            "messages": self.conversation_history,
            "max_tokens": 2000,
            "temperature": 0.7
        }
        
        # Add tools if available
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        # Make API call
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(OPENAI_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            # Print detailed error for debugging
            print(f"\n❌ API Error: {e}")
            if response.text:
                print(f"Response: {response.text[:500]}")
            # Print last few messages to debug
            print(f"\nLast message in history:")
            if self.conversation_history:
                print(json.dumps(self.conversation_history[-1], indent=2)[:500])
            raise
    
    def handle_response(self, response):
        """Handle LLM response and check for tool calls"""
        choice = response["choices"][0]
        message = choice["message"]
        
        # Fix: Ensure content is never null for AIML API compatibility
        if message.get("content") is None:
            message["content"] = ""
        
        # Add assistant message to history
        self.conversation_history.append(message)
        
        # Check if there are tool calls
        if message.get("tool_calls"):
            return {
                "type": "tool_calls",
                "tool_calls": message["tool_calls"]
            }
        else:
            return {
                "type": "text",
                "content": message.get("content", "")
            }
    
    def add_tool_result(self, tool_call_id, result):
        """Add tool execution result to conversation"""
        # Extract content from MCP result format
        if isinstance(result, dict):
            # MCP returns results in format: {"content": [{"type": "text", "text": "..."}]}
            if "content" in result and isinstance(result["content"], list):
                # Extract text from content array
                text_parts = []
                for item in result["content"]:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            text = item.get("text", "")
                            if text:  # Only add non-empty text
                                text_parts.append(text)
                        # Handle other content types if needed
                        elif "text" in item:
                            text = item.get("text", "")
                            if text:
                                text_parts.append(text)
                
                content = "\n\n".join(text_parts) if text_parts else "No content available"
                # DEBUG: Log extracted content
                print(f"   📝 Extracted content ({len(content)} chars): {content[:300]}...")
            else:
                # Fallback: convert entire result to JSON string
                content = json.dumps(result, ensure_ascii=False)
                print(f"   📝 Fallback JSON content: {content[:200]}...")
        elif isinstance(result, str):
            content = result if result else "Empty result"
            print(f"   📝 String content: {content[:200]}...")
        else:
            content = str(result) if result is not None else "No result"
            print(f"   📝 Other content: {content[:200]}...")
        
        # Final safety check: ensure content is never None or empty
        if not content or content.strip() == "":
            content = "Tool executed successfully but returned no content"
        
        # Ensure content is a valid string (no null bytes or other issues)
        content = str(content).replace('\x00', '')
        
        self.conversation_history.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content
        })
    
    def execute_tool_calls(self, tool_calls, tenant_id: str = None):
        """Execute tool calls via MCP clients and return results
        
        Args:
            tool_calls: List of tool calls from LLM
            tenant_id: Tenant ID from authenticated user (for PostgreSQL MCP queries)
        """
        results = []
        
        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_args = json.loads(tool_call["function"]["arguments"])
            tool_call_id = tool_call["id"]
            
            # Inject tenant_id for all MCP tools that require tenant isolation
            if tenant_id and tool_name in ["query", "query_knowledge_base", "list_documents"]:
                tool_args["tenant_id"] = tenant_id
                print(f"   → Calling {tool_name} with tenant_id: {tenant_id}")
            else:
                print(f"   → Calling {tool_name} with args: {tool_args}")
            
            # Find which MCP client has this tool
            result = None
            executed = False
            
            # Try all MCP clients
            for client in self.mcp_clients:
                # Check if this client has the tool
                client_tool_names = [t["name"] for t in client.tools]
                if tool_name in client_tool_names:
                    result = client.call_tool(tool_name, tool_args)
                    executed = True
                    break
            
            # Fallback to primary client
            if not executed and self.mcp_client:
                result = self.mcp_client.call_tool(tool_name, tool_args)
                executed = True
            
            if executed:
                # Debug: print result structure
                print(f"   ✓ Got result (type: {type(result).__name__})")
                
                # Debug: show first part of result
                if isinstance(result, dict) and "content" in result:
                    print(f"   📄 Content items: {len(result.get('content', []))}")
                
                results.append({"tool_call_id": tool_call_id, "result": result})
                
                # Add to conversation history
                self.add_tool_result(tool_call_id, result)
            else:
                print("   ⚠️  No MCP client found for this tool")
        
        return results
