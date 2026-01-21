"""
FastAPI dependencies for Eve Agent.
"""
from functools import lru_cache
from typing import List, Dict, Any
import os
from pathlib import Path

from .config import get_settings
from .services.llm_host import LLMHost
from .services.mcp_client import MCPClient

settings = get_settings()

# MCP Server Configuration
TAVILY_MCP_CONFIG = {
    "command": "npx",
    "args": ["-y", "tavily-mcp@0.1.3"],
    "env": {"TAVILY_API_KEY": None},  # Will be loaded from .env
}

POSTGRES_MCP_CONFIG = {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-postgres"],
    "env": {},
}

MEETING_RAG_MCP_CONFIG = {
    "command": "python",
    "args": ["../meeting_rag/mcp_server.py"],
    "env": {"PYTHONPATH": "../meeting_rag"},
}

RAG_SYSTEM_MCP_CONFIG = {
    "command": "python",
    "args": ["../mcp/server.py"],
    "env": {"PYTHONPATH": ".."},
}

# Global MCP clients and LLM host (initialized on startup)
_mcp_clients: List[MCPClient] = []
_llm_host: LLMHost | None = None
_all_tools: List[Dict[str, Any]] = []

# Session storage (in production, use Redis)
_user_sessions: Dict[str, Dict[str, Any]] = {}


def get_system_prompt() -> str:
    """Load system prompt from resources."""
    # Import here to avoid circular dependencies
    import sys
    # Add agent directory to path to access resources
    # dependencies.py is at: services/eve/src/eve_agent/dependencies.py
    # agent folder is at: services/eve/agent/
    # So we need to go: parent (eve_agent) -> parent (src) -> parent (eve) -> agent
    agent_dir = Path(__file__).parent.parent.parent / "agent"
    if str(agent_dir) not in sys.path:
        sys.path.insert(0, str(agent_dir))
    
    try:
        from resources.prompt_loader import get_initial_system_prompt
        return get_initial_system_prompt()
    except ImportError as e:
        # Fallback if resources not found
        print(f"Warning: Could not load system prompt from resources: {e}")
        return "You are Eve, an AI Chief of Staff assistant."


def initialize_mcp_clients():
    """Initialize all MCP clients and tools."""
    global _mcp_clients, _llm_host, _all_tools
    
    _mcp_clients = []
    _all_tools = []
    
    # Initialize Tavily
    print("📡 Connecting to Tavily MCP server...")
    tavily_config = TAVILY_MCP_CONFIG.copy()
    tavily_config["env"]["TAVILY_API_KEY"] = settings.tavily_api_key
    
    tavily_client = MCPClient(
        server_command=tavily_config["command"],
        server_args=tavily_config["args"],
        env=tavily_config["env"],
    )
    
    try:
        tavily_client.start()
        tavily_tools = tavily_client.get_tools_for_llm()
        _all_tools.extend(tavily_tools)
        _mcp_clients.append(tavily_client)
        print(f"✓ Tavily connected ({len(tavily_tools)} tools)")
    except Exception as e:
        print(f"❌ Tavily failed: {e}")
    
    # Initialize PostgreSQL
    print("📡 Connecting to PostgreSQL MCP server...")
    postgres_config = POSTGRES_MCP_CONFIG.copy()
    postgres_config["args"] = [
        "-y",
        "@modelcontextprotocol/server-postgres",
        settings.postgres_url.strip('"'),
    ]
    
    postgres_client = MCPClient(
        server_command=postgres_config["command"],
        server_args=postgres_config["args"],
        env=postgres_config["env"],
    )
    
    try:
        postgres_client.start()
        postgres_tools = postgres_client.get_tools_for_llm()
        _all_tools.extend(postgres_tools)
        _mcp_clients.append(postgres_client)
        print(f"✓ PostgreSQL connected ({len(postgres_tools)} tools)")
    except Exception as e:
        print(f"❌ PostgreSQL failed: {e}")
    
    # Initialize Meeting RAG
    print("📡 Connecting to Meeting RAG MCP server...")
    meeting_rag_client = MCPClient(
        server_command=MEETING_RAG_MCP_CONFIG["command"],
        server_args=MEETING_RAG_MCP_CONFIG["args"],
        env=MEETING_RAG_MCP_CONFIG["env"],
    )
    
    try:
        meeting_rag_client.start()
        meeting_rag_tools = meeting_rag_client.get_tools_for_llm()
        _all_tools.extend(meeting_rag_tools)
        _mcp_clients.append(meeting_rag_client)
        print(f"✓ Meeting RAG connected ({len(meeting_rag_tools)} tools)")
    except Exception as e:
        print(f"❌ Meeting RAG failed: {e}")
    
    # Initialize RAG System (Knowledge Base)
    print("📡 Connecting to RAG System MCP server...")
    rag_system_client = MCPClient(
        server_command=RAG_SYSTEM_MCP_CONFIG["command"],
        server_args=RAG_SYSTEM_MCP_CONFIG["args"],
        env=RAG_SYSTEM_MCP_CONFIG["env"],
    )
    
    try:
        rag_system_client.start()
        rag_system_tools = rag_system_client.get_tools_for_llm()
        _all_tools.extend(rag_system_tools)
        _mcp_clients.append(rag_system_client)
        print(f"✓ RAG System connected ({len(rag_system_tools)} tools)")
    except Exception as e:
        print(f"❌ RAG System failed: {e}")
    
    # Initialize LLM Host
    system_prompt = get_system_prompt()
    _llm_host = LLMHost(system_prompt=system_prompt, mcp_client=_mcp_clients[0] if _mcp_clients else None)
    _llm_host.mcp_clients = _mcp_clients
    _llm_host.add_mcp_tools(_all_tools)
    
    print(f"\n✓ Server ready with {len(_all_tools)} total tools")


def get_llm_host() -> LLMHost:
    """Get the LLM host instance."""
    if _llm_host is None:
        initialize_mcp_clients()
    return _llm_host


def get_all_tools() -> List[Dict[str, Any]]:
    """Get all available MCP tools."""
    if not _all_tools:
        initialize_mcp_clients()
    return _all_tools


def get_user_sessions() -> Dict[str, Dict[str, Any]]:
    """Get user sessions dictionary."""
    return _user_sessions
