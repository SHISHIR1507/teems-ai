# Notetaker Service

FastAPI microservice that integrates with Nylas to schedule meetings, capture transcripts, summaries, and action items, and provides RAG-powered chat functionality for querying meeting content.

## Features

- **Meeting Scheduling**: Schedule meetings with Nylas for automatic transcription
- **Webhook Processing**: Receives and processes Nylas webhook events for meeting media
- **Transcript Processing**: Extracts and stores meeting transcripts with speaker identification
- **RAG-Powered Chat**: Query meeting content using vector similarity search and LLM generation
- **Automatic Chunking**: Splits transcripts into chunks for efficient vector search
- **Embeddings**: Creates vector embeddings for semantic search using AIML API

## 🏗️ Architecture

The service follows FastAPI best practices with a clean, modular structure:

```
app/
├── core/                   # Core application components
│   ├── config.py          # Environment configuration & settings
│   └── database.py        # Database setup & session management
├── models/                 # SQLAlchemy database models
│   └── call.py            # Call & CallChunk models
├── schemas/                # Pydantic request/response models
│   └── request.py         # API request schemas
├── services/               # Business logic layer
│   ├── chunker.py         # Text chunking utility
│   ├── embeddings.py      # AIML embeddings service
│   ├── llm.py             # AIML LLM service
│   └── rag_service.py     # RAG processing service
└── routers/                # API endpoint handlers
    ├── meetings.py         # Meeting scheduling & chat endpoints
    ├── webhooks.py        # Nylas webhook handlers
    └── health.py          # Health check endpoint
```

## 📋 Prerequisites

- Python 3.9+
- PostgreSQL database with pgvector extension
- API keys for:
  - Nylas API (for meeting transcription)
  - AIML API (for embeddings and LLM)

## 🚀 Local Setup

### 1. Install Dependencies

```bash
cd services/agents/notetaker
pip install -r requirements.txt
```

### 2. Set Up PostgreSQL with pgvector

Ensure PostgreSQL is running and create a database:

```bash
# Create database
createdb notetaker_db

# Connect to PostgreSQL and enable pgvector extension
psql notetaker_db
CREATE EXTENSION IF NOT EXISTS vector;
\q
```

### 3. Configure Environment Variables

Create a `.env` file in the `notetaker` directory:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/notetaker_db

# Nylas API
NYLAS_API_KEY=your_nylas_api_key
NYLAS_BASE_URL=https://api.us.nylas.com

# AIML API (for embeddings and LLM)
AIML_API_KEY=your_aiml_api_key
AIML_BASE_URL=https://api.aimlapi.com/v1
EMBEDDING_MODEL=text-embedding-3-small
LLM_MODEL=gpt-4o
```

**Note**: If `AIML_API_KEY` is not set, the service will use dummy embeddings/LLM responses for testing.

### 4. Initialize Database

The database tables will be created automatically when you start the service. The `init_db()` function in `app/core/database.py` will:
- Create the `vector` extension if it doesn't exist
- Create the `calls` and `call_chunks` tables

### 5. Start the Server

```bash
# From the notetaker directory
uvicorn main:app --reload --port 8000
```

Or using Python directly:

```bash
python -m uvicorn main:app --reload --port 8000
```

The service will be available at `http://localhost:8000`

## 🧪 Testing Endpoints

### 1. Health Check

```bash
curl http://localhost:8000/health
```

**Expected Response:**
```json
{
  "status": "backend running"
}
```

### 2. Schedule a Meeting

```bash
curl -X POST http://localhost:8000/schedule-notetaker \
  -H "Content-Type: application/json" \
  -d '{
    "meeting_link": "https://zoom.us/j/123456789",
    "start_time": "2024-12-25T14:30:00Z"
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Meeting scheduled and saved",
  "call_id": "uuid-here",
  "meeting_saved": {
    "id": "uuid-here",
    "title": "Teems.ai",
    "meeting_link": "https://zoom.us/j/123456789",
    "start_time": "2024-12-25T14:30:00Z",
    "created_at": "2024-12-20T10:00:00Z"
  },
  "nylas_response": {...}
}
```

**Note**: The `start_time` must be in the future and in ISO format (e.g., `2024-12-25T14:30:00Z`).

### 3. Chat About a Meeting

After a meeting has been processed (transcript available), you can query it:

```bash
curl -X POST http://localhost:8000/meetings/{call_id}/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What were the main action items?"
  }'
```

**Expected Response:**
```json
{
  "answer": "Based on the meeting context...",
  "meeting_title": "Teems.ai",
  "chunks_used": 3,
  "query": "What were the main action items?"
}
```

### 4. Webhook Endpoint (for Nylas)

The webhook endpoint is used by Nylas to send meeting events. For local testing, you can use a tool like [ngrok](https://ngrok.com/) to expose your local server:

```bash
# Install ngrok
brew install ngrok  # macOS
# or download from https://ngrok.com/

# Expose local server
ngrok http 8000

# Use the ngrok URL in Nylas webhook configuration:
# https://your-ngrok-url.ngrok.io/webhooks/nylas
```

**Webhook Verification (GET):**
```bash
curl "http://localhost:8000/webhooks/nylas?challenge=test123"
```

**Webhook Event (POST):**
Nylas will POST events to this endpoint automatically when meeting media is ready.

## 📚 API Endpoints

### `POST /schedule-notetaker`
Schedule a meeting with Nylas for transcription.

**Request Body:**
```json
{
  "meeting_link": "string (required)",
  "start_time": "string (required, ISO format)"
}
```

**Response:** Meeting details with call_id

---

### `POST /meetings/{call_id}/chat`
Query a meeting using RAG-powered chat.

**Path Parameters:**
- `call_id` (string): The meeting ID from scheduling

**Request Body:**
```json
{
  "query": "string (required)"
}
```

**Response:** LLM-generated answer with context

**Error Responses:**
- `404`: Meeting not found
- `400`: No transcript available or query missing

---

### `GET /health`
Health check endpoint.

**Response:** Service status

---

### `GET /webhooks/nylas`
Webhook verification endpoint (for Nylas).

**Query Parameters:**
- `challenge` (string): Verification challenge string

**Response:** Returns the challenge string

---

### `POST /webhooks/nylas`
Webhook event handler (for Nylas).

**Request Body:** Nylas webhook payload

**Response:** `OK` (text/plain)

## 🔍 How It Works

1. **Scheduling**: When you schedule a meeting, it's saved to the database and sent to Nylas
2. **Webhook Processing**: Nylas sends webhook events when meeting media is ready
3. **Transcript Extraction**: The service fetches transcripts, summaries, and action items from Nylas
4. **RAG Processing**: Transcripts are chunked and embedded for vector search
5. **Chat Queries**: Users can query meetings using natural language, which uses vector similarity to find relevant chunks and generates answers with LLM

## 🐛 Troubleshooting

### Database Connection Issues

```bash
# Check if PostgreSQL is running
pg_isready

# Verify database exists
psql -l | grep notetaker_db

# Check pgvector extension
psql notetaker_db -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
```

### Missing Environment Variables

The service will print warnings if required environment variables are missing:
- `DATABASE_URL` - Required, will raise error if missing
- `NYLAS_API_KEY` - Required for scheduling meetings
- `AIML_API_KEY` - Optional, will use dummy responses if missing

### Webhook Not Receiving Events

1. Verify webhook URL is accessible (use ngrok for local testing)
2. Check Nylas dashboard for webhook configuration
3. Check service logs for incoming webhook requests
4. Verify meeting was scheduled successfully

### RAG Not Working

1. Ensure transcript exists: Check `call.transcript` in database
2. Verify embeddings are created: Check `call_chunks` table has records
3. Check AIML API key is set correctly
4. Review service logs for embedding/LLM errors

## 📝 Development Notes

- The service automatically creates database tables on startup
- Transcripts are chunked into ~500 word chunks for RAG
- Vector embeddings use 1536 dimensions (OpenAI text-embedding-3-small)
- Top 5 most relevant chunks are used for context in chat responses
- Webhook events are stored in memory (last 50 events) for debugging

## 🔗 Related Services

- **Nylas API**: Meeting transcription and recording
- **AIML API**: Embeddings and LLM generation
- **PostgreSQL + pgvector**: Vector database for semantic search
