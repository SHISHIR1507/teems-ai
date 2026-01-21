# Meeting RAG MCP Server

This is an MCP (Model Context Protocol) server that provides meeting transcript search and RAG-based Q&A capabilities.

## 📁 Files Overview

### Core MCP Server (REQUIRED)
- **`mcp_server.py`** ⭐ - Main MCP server (THIS IS WHAT RUNS)
  - Exposes 4 tools: `search_meetings`, `list_meetings`, `get_meeting_details`, `ask_meeting_question`
  - Communicates via stdio using MCP protocol

### Database Layer (REQUIRED)
- **`database.py`** - SQLAlchemy database connection
- **`models.py`** - Database models (Call, CallChunk)

### RAG Components (REQUIRED)
- **`rag_service.py`** - RAG logic (search chunks, generate answers)
- **`embeddings.py`** - AIML API embeddings provider
- **`chunker.py`** - Simple text chunking utility
- **`llm.py`** - AIML API LLM client for answer generation

### Other Files (NOT used by MCP server)
- **`main.py`** ❌ - Separate FastAPI webhook server for Nylas integration (NOT part of MCP)
- **`.env`** - Environment configuration

## 🚀 How It Works

The MCP server is started automatically by Eve's agent when configured in `agent/eve_config.py`:

```python
MEETING_RAG_MCP_CONFIG = {
    "command": "python",
    "args": ["../meeting_rag/mcp_server.py"],
    "env": {"PYTHONPATH": "../meeting_rag"},
}
```

**Important:** The MCP server does NOT do embeddings itself. It uses the AIML API for:
- Generating embeddings (via `embeddings.py`)
- Generating answers (via `llm.py`)

## 🔧 Environment Variables

Create a `.env` file with:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/meetings_db
AIML_API_KEY=your_aiml_api_key
AIML_BASE_URL=https://api.aimlapi.com/v1
EMBEDDING_MODEL=text-embedding-3-small
LLM_MODEL=gpt-4o
```

## 🛠️ MCP Tools Exposed

1. **search_meetings** - Vector search across all meeting transcripts
   - Parameters: `query` (string), `top_k` (int, default 5)
   
2. **list_meetings** - List all meetings with metadata
   - Parameters: `limit` (int, default 10)
   
3. **get_meeting_details** - Get full transcript, summary, action items
   - Parameters: `call_id` (string)
   
4. **ask_meeting_question** - RAG-based Q&A about a specific meeting
   - Parameters: `call_id` (string), `question` (string)

## 📊 Database Schema

```sql
CREATE TABLE calls (
    id VARCHAR PRIMARY KEY,
    meeting_id VARCHAR,
    title VARCHAR,
    meeting_link TEXT,
    start_time TIMESTAMP,
    transcript TEXT,
    summary TEXT,
    action_items JSON,
    created_at TIMESTAMP
);

CREATE TABLE call_chunks (
    id VARCHAR PRIMARY KEY,
    call_id VARCHAR REFERENCES calls(id),
    chunk_index INTEGER,
    content_type VARCHAR,
    content TEXT,
    embedding vector(1536),
    created_at TIMESTAMP
);
```

## 🔗 Integration with Eve

This MCP server is used by Eve (the AI agent) to:
- Search meeting transcripts semantically
- Answer questions about past meetings
- Retrieve meeting summaries and action items
- List available meetings

The embedding and LLM generation are handled by this server using AIML API, not by the main agent.

## 📝 Dependencies

See `requirements.txt` for minimal dependencies:
- `mcp` - MCP protocol
- `sqlalchemy`, `psycopg2-binary`, `pgvector` - Database
- `numpy` - Vector operations
- `python-dotenv`, `requests` - Utilities

Note: `openai` package is NOT needed as we use AIML API directly via requests.
