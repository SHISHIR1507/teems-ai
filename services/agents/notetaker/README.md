# Notetaker Agent Service

FastAPI microservice that integrates with Nylas to schedule meetings, capture transcripts, summaries, and action items, and provides RAG-powered chat functionality for querying meeting content.

## Features

- **Meeting Scheduling**: Schedule meetings with Nylas for automatic transcription
- **Webhook Processing**: Receives and processes Nylas webhook events for meeting media
- **Transcript Processing**: Extracts and stores meeting transcripts with speaker identification
- **RAG-Powered Chat**: Query meeting content using vector similarity search and LLM generation
- **Automatic Chunking**: Splits transcripts into chunks for efficient vector search
- **Embeddings**: Creates vector embeddings for semantic search using AIML API
- **Multi-Tenant Support**: Full tenant isolation with Auth0 authentication
- **Comprehensive API**: RESTful API with versioning (`/v1/`)

## 🏗️ Architecture

The service follows FastAPI best practices with a clean, modular structure:

```
services/agents/notetaker/
├── app/
│   ├── api/
│   │   └── routes/          # API endpoint handlers
│   │       ├── calls.py     # Call management endpoints
│   │       ├── meetings.py  # Meeting scheduling & chat
│   │       ├── webhooks.py  # Nylas webhook handlers
│   │       └── health.py    # Health check
│   ├── core/                 # Core application components
│   │   ├── auth.py          # Auth0 JWT verification
│   │   ├── config.py        # Environment configuration
│   │   ├── database.py      # Database setup & session management
│   │   └── dependencies.py  # FastAPI dependencies
│   ├── models/               # SQLAlchemy database models
│   │   └── call.py          # Call & CallChunk models
│   ├── schemas/              # Pydantic request/response models
│   │   ├── request.py       # API request schemas
│   │   └── response.py      # API response schemas
│   ├── services/             # Business logic layer
│   │   ├── chunker.py       # Text chunking utility
│   │   ├── embeddings.py    # AIML embeddings service
│   │   ├── llm.py           # AIML LLM service
│   │   ├── nylas_service.py # Nylas API abstraction
│   │   ├── rag_service.py   # RAG processing service
│   │   └── db_helpers.py    # Database helper functions
│   └── main.py              # FastAPI application
├── main.py                   # Entry point
├── Dockerfile
├── README.md
└── requirements.txt
```

## 📋 Prerequisites

- Python 3.9+
- PostgreSQL database with pgvector extension
- API keys for:
  - Nylas API (for meeting transcription)
  - AIML API (for embeddings and LLM)
  - Auth0 (for authentication)

## 🚀 Local Setup

### 1. Install Dependencies

```bash
cd services/agents/notetaker
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
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
# Database (Required)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/notetaker_db

# Nylas API (Required)
NYLAS_API_KEY=your_nylas_api_key
NYLAS_BASE_URL=https://api.us.nylas.com

# AIML API (Required for embeddings and LLM)
AIML_API_KEY=your_aiml_api_key
AIML_BASE_URL=https://api.aimlapi.com/v1
EMBEDDING_MODEL=text-embedding-3-small
LLM_MODEL=gpt-4o

# Auth0 (Required)
AUTH0_DOMAIN=your-tenant.auth0.com
AUTH0_AUDIENCE=https://api.teems.ai
AUTH0_ALGORITHM=RS256
```

**Note**: If `AIML_API_KEY` is not set, the service will use dummy embeddings/LLM responses for testing.

### 4. Initialize Database

The database tables will be created automatically when you start the service. The `init_db()` function in `app/core/database.py` will:
- Create the `vector` extension if it doesn't exist
- Create the `calls` and `call_chunks` tables

### 5. Start the Server

```bash
# From the notetaker directory
export PYTHONPATH=app
uvicorn app.main:app --reload --port 8000
```

Or using Python directly:

```bash
python -m uvicorn app.main:app --reload --port 8000
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
curl -X POST http://localhost:8000/v1/meetings/schedule \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_AUTH0_TOKEN" \
  -d '{
    "meeting_link": "https://zoom.us/j/123456789",
    "start_time": "2024-12-25T14:30:00Z",
    "title": "Team Standup"
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Meeting scheduled and saved",
  "call_id": "uuid-here",
  "call": {
    "id": "uuid-here",
    "title": "Team Standup",
    "meeting_link": "https://zoom.us/j/123456789",
    "start_time": "2024-12-25T14:30:00Z",
    "status": "scheduled",
    ...
  },
  "nylas_meeting_id": "nylas-id-here"
}
```

**Note**: The `start_time` must be in the future and in ISO format (e.g., `2024-12-25T14:30:00Z`).

### 3. List Calls

```bash
curl -X GET "http://localhost:8000/v1/calls?limit=10&offset=0" \
  -H "Authorization: Bearer YOUR_AUTH0_TOKEN"
```

### 4. Get Call Details

```bash
curl -X GET http://localhost:8000/v1/calls/{call_id} \
  -H "Authorization: Bearer YOUR_AUTH0_TOKEN"
```

### 5. Chat Across Meetings (Recommended)

After meetings have been processed (transcripts available), you can ask questions
across **all meetings attended by the authenticated user**:

```bash
curl -X POST http://localhost:8000/v1/meetings/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_AUTH0_TOKEN" \
  -d '{
    "query": "What were the main action items from my recent meetings?"
  }'
```

**Expected Response:**
```json
{
  "answer": "Based on your recent meetings...",
  "meeting_title": "Multiple meetings",
  "chunks_used": 5,
  "query": "What were the main action items from my recent meetings?",
  "sources": [
    {
      "call_id": "uuid-1",
      "meeting_title": "Team Standup",
      "snippet_preview": "Alice: We need to ship..."
    },
    {
      "call_id": "uuid-2",
      "meeting_title": "Product Review",
      "snippet_preview": "Bob: Let's prioritize..."
    }
  ],
  "deprecated_endpoint": false
}
```

### 6. Chat About a Single Meeting (Deprecated)

After a meeting has been processed (transcript available), you can query it:

```bash
curl -X POST http://localhost:8000/v1/meetings/{call_id}/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_AUTH0_TOKEN" \
  -d '{
    "query": "What were the main action items?"
  }'
```

**Expected Response:**
```json
{
  "answer": "Based on the meeting context...",
  "meeting_title": "Team Standup",
  "chunks_used": 3,
  "query": "What were the main action items?",
  "sources": [
    {
      "call_id": "uuid-here",
      "meeting_title": "Team Standup",
      "snippet_preview": null
    }
  ],
  "deprecated_endpoint": true
}
```

### 6. Get Transcript

```bash
curl -X GET http://localhost:8000/v1/calls/{call_id}/transcript \
  -H "Authorization: Bearer YOUR_AUTH0_TOKEN"
```

### 7. Get Summary

```bash
curl -X GET http://localhost:8000/v1/calls/{call_id}/summary \
  -H "Authorization: Bearer YOUR_AUTH0_TOKEN"
```

### 8. Get Action Items

```bash
curl -X GET http://localhost:8000/v1/calls/{call_id}/action-items \
  -H "Authorization: Bearer YOUR_AUTH0_TOKEN"
```

### 9. Delete Call

```bash
curl -X DELETE http://localhost:8000/v1/calls/{call_id} \
  -H "Authorization: Bearer YOUR_AUTH0_TOKEN"
```

### 10. Webhook Endpoint (for Nylas)

The webhook endpoint is used by Nylas to send meeting events. For local testing, you can use a tool like [ngrok](https://ngrok.com/) to expose your local server:

```bash
# Install ngrok
brew install ngrok  # macOS
# or download from https://ngrok.com/

# Expose local server
ngrok http 8000

# Use the ngrok URL in Nylas webhook configuration:
# https://your-ngrok-url.ngrok.io/v1/webhooks/nylas
```

**Webhook Verification (GET):**
```bash
curl "http://localhost:8000/v1/webhooks/nylas?challenge=test123"
```

**Webhook Event (POST):**
Nylas will POST events to this endpoint automatically when meeting media is ready.

## 📚 API Endpoints

### Authentication

All endpoints (except `/health` and `/v1/webhooks/nylas`) require authentication via Auth0 JWT token in the `Authorization` header:

```
Authorization: Bearer YOUR_AUTH0_TOKEN
```

### Meetings

#### `POST /v1/meetings/schedule`
Schedule a meeting with Nylas for transcription.

**Request Body:**
```json
{
  "meeting_link": "string (required)",
  "start_time": "string (required, ISO format)",
  "title": "string (required)"
}
```

**Response:** `ScheduleMeetingResponse` with call details

---

#### `POST /v1/meetings/chat`
Global chat across all completed meetings for the authenticated user.

**Request Body:**
```json
{
  "query": "string (required)"
}
```

**Response:** `ChatResponse` with AI-generated answer

The response includes:
- `answer`: AI-generated answer
- `meeting_title`: Either a single meeting title or `"Multiple meetings"`
- `chunks_used`: Number of context chunks used
- `query`: Original query
- `sources`: Optional list of meetings used as sources (call_id, meeting_title, snippet_preview)
- `deprecated_endpoint`: `false` for this endpoint

---

#### `POST /v1/meetings/{call_id}/chat` (Deprecated)
Query a single meeting using RAG-powered chat.

**Path Parameters:**
- `call_id` (string): The meeting ID from scheduling

**Request Body:**
```json
{
  "query": "string (required)"
}
```

**Response:** `ChatResponse` with AI-generated answer

The response is the same shape as the global endpoint, but will have:
- `sources`: A single entry pointing to this call
- `deprecated_endpoint`: `true` (this endpoint is kept for backward compatibility)

**Error Responses:**
- `404`: Meeting not found
- `400`: No transcript available or query missing

---

### Calls

#### `GET /v1/calls`
List calls for the authenticated tenant.

**Query Parameters:**
- `limit` (int, default=50): Number of results per page (1-100)
- `offset` (int, default=0): Pagination offset
- `status` (string, optional): Filter by status (scheduled, processing, completed, failed)

**Response:** `CallListResponse` with paginated calls

---

#### `GET /v1/calls/{call_id}`
Get call details by ID.

**Response:** `CallResponse` with full call details

**Error Responses:**
- `404`: Call not found

---

#### `DELETE /v1/calls/{call_id}`
Delete a call.

**Response:** Success message

**Error Responses:**
- `404`: Call not found

---

#### `GET /v1/calls/{call_id}/transcript`
Get raw transcript for a call.

**Response:** Transcript text

**Error Responses:**
- `404`: Call not found or transcript not available

---

#### `GET /v1/calls/{call_id}/summary`
Get summary for a call.

**Response:** Summary text

**Error Responses:**
- `404`: Call not found or summary not available

---

#### `GET /v1/calls/{call_id}/action-items`
Get action items for a call.

**Response:** Action items JSON

**Error Responses:**
- `404`: Call not found or action items not available

---

### Webhooks

#### `GET /v1/webhooks/nylas`
Webhook verification endpoint (for Nylas).

**Query Parameters:**
- `challenge` (string): Verification challenge string

**Response:** Returns the challenge string

---

#### `POST /v1/webhooks/nylas`
Webhook event handler (for Nylas).

**Request Body:** Nylas webhook payload

**Response:** `OK` (text/plain)

---

### Health

#### `GET /health`
Health check endpoint.

**Response:** Service status

---

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
- `AUTH0_DOMAIN`, `AUTH0_AUDIENCE` - Required for authentication

### Authentication Issues

- Verify Auth0 token is valid and not expired
- Check that token includes `tenant_id` claim
- Ensure `AUTH0_DOMAIN` and `AUTH0_AUDIENCE` are correctly configured

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
- All operations are tenant-isolated for security
- Webhook events are stored in memory (last 50 events) for debugging

## 🔗 Related Services

- **Nylas API**: Meeting transcription and recording
- **AIML API**: Embeddings and LLM generation
- **PostgreSQL + pgvector**: Vector database for semantic search
- **Auth0**: Authentication and authorization

## 🚀 Deployment

The service is containerized and can be deployed to ECS or Kubernetes. See infrastructure configuration for deployment details.

### Docker Build

```bash
docker build -t notetaker-service .
docker run -p 8000:8000 --env-file .env notetaker-service
```

## 📄 License

Proprietary - Teems AI
