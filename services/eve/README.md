# Eve - AI Chief of Staff with RAG & MCP Integration

Eve is an intelligent AI assistant powered by GPT-5.2 that combines web search, database operations, meeting insights, and document knowledge base capabilities through Model Context Protocol (MCP) servers.

## 🌟 Features

- **Multi-Modal AI Chat** - Conversational interface with streaming responses
- **Web Search** - Real-time internet search via Tavily MCP
- **Database Operations** - PostgreSQL integration for data storage and retrieval
- **Meeting RAG** - Search and query meeting transcripts with semantic search
- **Document Knowledge Base** - Upload and query documents (PDF, DOCX) with vector search
- **Smart Recommendations** - Context-aware action suggestions based on conversation
- **FastAPI Backend** - High-performance async API with automatic documentation

## 📁 Project Structure

```
services/eve/
├── main.py                          # Entry point
├── src/
│   └── eve_agent/                   # Main package
│       ├── app.py                   # FastAPI app creation
│       ├── config.py                # Configuration
│       ├── dependencies.py          # MCP initialization
│       ├── api/
│       │   └── routes.py            # API endpoints
│       ├── models/                  # Database models
│       ├── schemas/                 # Pydantic schemas
│       ├── services/                # Business logic
│       │   ├── llm_host.py
│       │   ├── mcp_client.py
│       │   ├── rag/                # RAG services
│       │   └── recommendation/     # Recommendation engine
│       └── database/                # Database setup
├── agent/
│   └── resources/                   # Prompts and agent definitions
├── mcp/                            # Document RAG MCP Server
├── meeting_rag/                    # Meeting RAG MCP Server
├── requirements.txt
└── README.md
```

## 🚀 Local Development & Testing

### Prerequisites

1. **Python 3.11+**
   ```bash
   python --version  # Should be 3.11 or higher
   ```

2. **PostgreSQL with pgvector extension**
   ```bash
   # Install PostgreSQL (if not already installed)
   # macOS: brew install postgresql
   # Ubuntu: sudo apt-get install postgresql postgresql-contrib
   
   # Install pgvector extension
   # macOS: brew install pgvector
   # Or compile from source: https://github.com/pgvector/pgvector
   ```

3. **Node.js and npm** (for MCP servers)
   ```bash
   node --version   # Should be 16+ 
   npm --version
   ```
   Download from: https://nodejs.org/

### Step 1: Clone and Navigate

```bash
cd services/eve
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# macOS/Linux:
source venv/bin/activate
# Windows:
# venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Note:** The `sentence-transformers` and `torch` packages are large. Installation may take a few minutes.

### Step 4: Set Up Database

1. **Create PostgreSQL database:**
   ```bash
   # Connect to PostgreSQL
   psql -U postgres
   
   # Create database
   CREATE DATABASE eve_db;
   
   # Connect to the new database
   \c eve_db
   
   # Enable pgvector extension
   CREATE EXTENSION IF NOT EXISTS vector;
   
   # Exit psql
   \q
   ```

2. **Run database migrations:**
   ```bash
   # From services/eve directory
   python migrate_db.py
   ```

   This will create the `documents` and `document_chunks` tables with pgvector support.

### Step 5: Configure Environment Variables

Create a `.env` file in the `services/eve/agent/` directory:

```bash
cd agent
touch .env
```

Add the following to `agent/.env`:

```env
# Database (REQUIRED)
DATABASE_URL=postgresql://username:password@localhost:5432/eve_db

# AIML API (REQUIRED)
AIML_API_KEY=your_aiml_api_key_here

# Tavily API (OPTIONAL - for web search)
TAVILY_API=your_tavily_api_key_here

# AWS S3 (OPTIONAL - for document storage)
# If not provided, S3 features will be disabled
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1
S3_BUCKET_NAME=your_bucket_name
S3_FOLDER_PREFIX=UserUploads

# Optional Configuration
EMBEDDING_MODEL=text-embedding-3-small
LLM_MODEL=gpt-4o-mini
CHUNK_SIZE=350
CHUNK_OVERLAP=50
```

**Important Notes:**
- Replace `username`, `password`, and `eve_db` with your PostgreSQL credentials
- Get AIML API key from: https://aimlapi.com/
- Get Tavily API key from: https://tavily.com/ (optional)
- S3 credentials are optional - if not provided, document uploads will fail but chat will work

### Step 6: Run the Server

From the `services/eve` directory:

```bash
# Option 1: Using Python directly
python main.py

# Option 2: Using uvicorn directly (with auto-reload)
uvicorn main:app --reload --host 0.0.0.0 --port 5000
```

You should see output like:
```
🚀 Starting Eve Web Server...
==================================================
📡 Connecting to Tavily MCP server...
✓ Tavily connected (2 tools)
📡 Connecting to PostgreSQL MCP server...
✓ PostgreSQL connected (3 tools)
...
✓ Server ready with X total tools
🌐 Server ready
```

### Step 7: Verify Server is Running

1. **Health Check:**
   ```bash
   curl http://localhost:5000/health
   ```
   Should return: `{"status":"ok"}`

2. **API Documentation:**
   - Open in browser: http://localhost:5000/docs
   - Alternative docs: http://localhost:5000/redoc

3. **Test Chat Endpoint:**
   ```bash
   curl -X POST http://localhost:5000/api/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "Hello, Eve!", "session_id": "test123"}'
   ```

## 🧪 Testing Endpoints

### Health Check
```bash
curl http://localhost:5000/health
```

### Chat with Eve (SSE Streaming)
```bash
curl -N -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is artificial intelligence?", "session_id": "test123"}'
```

The `-N` flag enables streaming so you can see the SSE events in real-time.

### Upload Document
```bash
curl -X POST http://localhost:5000/api/documents/upload \
  -F "file=@/path/to/your/document.pdf" \
  -F "tenant_id=default"
```

**Note:** Requires S3 credentials to be configured.

### List Documents
```bash
curl http://localhost:5000/api/documents?tenant_id=default
```

### Reset Conversation
```bash
curl -X POST http://localhost:5000/api/reset \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test123"}'
```

## 🔧 API Endpoints

### Chat & Conversation
- `GET /health` - Health check endpoint
- `POST /api/chat` - Chat with Eve (SSE streaming)
- `POST /api/reset` - Reset conversation history
- `POST /api/action_clicked` - Track recommendation clicks

### Document Management
- `POST /api/documents/upload` - Upload documents for RAG
- `GET /api/documents` - List uploaded documents

### Documentation
- `GET /docs` - Swagger UI documentation
- `GET /redoc` - ReDoc documentation
- `GET /openapi.json` - OpenAPI schema

## 🧩 MCP Servers

Eve integrates with 4 MCP servers (automatically started):

### 1. Tavily MCP (Web Search)
- **Command**: `npx -y tavily-mcp@0.1.3`
- **Tools**: `tavily-search`, `tavily-extract`
- **Purpose**: Real-time internet search
- **Required**: `TAVILY_API` in `.env`

### 2. PostgreSQL MCP (Database)
- **Command**: `npx -y @modelcontextprotocol/server-postgres`
- **Tools**: `query`, `list_tables`, `describe_table`
- **Purpose**: Database operations
- **Required**: `DATABASE_URL` in `.env`

### 3. Meeting RAG MCP (Local)
- **Command**: `python ../meeting_rag/mcp_server.py`
- **Tools**: `search_meetings`, `list_meetings`, `get_meeting_details`, `ask_meeting_question`
- **Purpose**: Meeting transcript search and Q&A

### 4. Document RAG MCP (Local)
- **Command**: `python ../mcp/server.py`
- **Tools**: `query_knowledge_base`, `list_documents`
- **Purpose**: Document knowledge base search

## 🐛 Troubleshooting

### Database Connection Issues

**Error:** `could not connect to server` or `database does not exist`

**Solution:**
1. Verify PostgreSQL is running:
   ```bash
   # macOS
   brew services list | grep postgresql
   
   # Linux
   sudo systemctl status postgresql
   ```

2. Check DATABASE_URL format:
   ```
   DATABASE_URL=postgresql://username:password@localhost:5432/eve_db
   ```

3. Test connection:
   ```bash
   psql $DATABASE_URL -c "SELECT version();"
   ```

### pgvector Extension Not Found

**Error:** `extension "vector" does not exist`

**Solution:**
```bash
psql $DATABASE_URL -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### MCP Server Connection Failures

**Error:** `❌ Tavily failed` or `❌ PostgreSQL failed`

**Solutions:**
1. **Tavily:** Ensure `TAVILY_API` is set in `.env` (optional, service will continue without it)
2. **PostgreSQL MCP:** Ensure Node.js and npm are installed
3. **Local MCP servers:** Check Python paths are correct

### Import Errors

**Error:** `ModuleNotFoundError: No module named 'eve_agent'`

**Solution:**
- Always run from `services/eve/` directory
- Ensure `src/` directory is in Python path (handled by `main.py`)

### Port Already in Use

**Error:** `Address already in use`

**Solution:**
```bash
# Find process using port 5000
lsof -i :5000

# Kill the process (replace PID with actual process ID)
kill -9 <PID>

# Or use a different port
uvicorn main:app --port 5001
```

### S3 Upload Failures

**Error:** `Failed to upload file to S3`

**Solutions:**
1. Verify AWS credentials are correct in `.env`
2. Check S3 bucket exists and is accessible
3. Verify IAM permissions for S3 access
4. **For local testing:** S3 is optional - you can test chat without document uploads

## 🛠️ Development Tips

### Running with Auto-Reload

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 5000
```

Changes to Python files will automatically restart the server.

### Testing Individual Components

**Test MCP servers independently:**
```bash
# Test Meeting RAG MCP
cd meeting_rag
python mcp_server.py

# Test Document RAG MCP
cd mcp
python server.py
```

**Test database connection:**
```bash
python -c "from src.eve_agent.database.session import SessionLocal; db = next(SessionLocal()); print('DB connected!')"
```

### Debugging

1. **Enable debug logging:**
   ```env
   LOG_LEVEL=debug
   ENV=development
   ```

2. **Check logs:**
   - Server logs appear in console
   - MCP server errors are printed to stderr

3. **Database queries:**
   ```bash
   psql $DATABASE_URL
   \dt  # List tables
   SELECT * FROM documents LIMIT 5;
   ```

## 🚢 Production Deployment

The service is automatically deployed to AWS ECS when code is pushed to the `main` branch.

See deployment files:
- `.github/workflows/deploy-eve-ecs.yml` - GitHub Actions workflow
- `infra/ecs-eve-stack.yaml` - CloudFormation template
- `Dockerfile` - Container definition

### Required GitHub Secrets

- `DATABASE_URL` or `EVE_DATABASE_URL`
- `S3_BUCKET_NAME` or `EVE_S3_BUCKET_NAME`
- `AIML_API_KEY` or `EVE_AIML_API_KEY`
- `TAVILY_API` or `EVE_TAVILY_API` (optional)
- `SSL_CERTIFICATE_ARN` or `EVE_SSL_CERTIFICATE_ARN` (optional, for HTTPS)

## 📊 Database Schema

### Documents Table
```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY,
    tenant_id VARCHAR(128),
    title VARCHAR(255),
    filename VARCHAR(255),
    s3_url TEXT,
    s3_key TEXT,
    file_size_bytes BIGINT,
    status VARCHAR(50),
    total_chunks INTEGER,
    metadata JSONB,
    created_at TIMESTAMP
);
```

### Document Chunks Table
```sql
CREATE TABLE document_chunks (
    id UUID PRIMARY KEY,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    tenant_id VARCHAR(128),
    chunk_index INTEGER,
    content TEXT,
    embedding vector(1536),
    metadata JSONB,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

## 📝 License

[Your License Here]

## 🤝 Contributing

[Your Contributing Guidelines Here]

## 📧 Support

[Your Support Contact Here]
