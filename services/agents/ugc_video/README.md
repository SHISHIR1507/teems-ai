# UGC Video Orchestrator Agent

An agentic workflow system for generating User-Generated Content (UGC) videos with AI. Uses CrewAI agents to orchestrate script generation, audio synthesis, image generation, and video creation with PostgreSQL persistence and AWS S3 storage.

## Tech Stack

### Backend
- **Framework**: FastAPI with async/await support
- **AI Orchestration**: CrewAI for multi-agent workflows
- **LLMs**: OpenAI GPT-4o, Google Gemini (via google-genai)
- **Database**: PostgreSQL with SQLAlchemy (async)
- **Storage**: AWS S3 for all media assets
- **Observability**: LangSmith for agent tracing
- **Authentication**: Auth0 JWT with tenant isolation

### Frontend
- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **HTTP Client**: Axios
- **State Management**: React hooks

## 🏗️ Architecture

The service follows FastAPI and CrewAI best practices with a clean, modular structure:

```
app/
├── main.py                 # FastAPI application entry point
├── api/routes/             # API endpoint handlers
│   ├── brand_sync.py       # Brand context synchronization
│   ├── ugc.py              # UGC image/video generation
│   └── conversation.py     # Conversation management
├── core/                   # Core application components
│   ├── config.py           # Environment configuration
│   ├── database.py         # SQLAlchemy models
│   └── dependencies.py     # FastAPI dependencies
├── models/                 # Pydantic schemas
│   └── schemas.py          # Request/response models
├── services/               # Business logic layer
│   ├── db_helpers.py       # Database CRUD operations
│   └── s3_utils.py         # S3 storage utilities
├── agents/                 # CrewAI agents
│   ├── chat_agent.py       # Conversational agent (Kai)
│   ├── prompt_agent.py     # Prompt variator agent
│   ├── image_agent.py      # Image generator agent
│   ├── script_agent.py     # Script generator agent
│   ├── audio_video_agent.py # Audio/video generator agent
│   └── lipsync_agent.py    # Lipsync agent
├── tools/                  # CrewAI tools
│   ├── prompt_variator.py  # GPT-5.2 vision prompt generation
│   ├── banana_ugc.py       # Google Nano Banana image generation
│   ├── script_maker.py     # Script generation tool
│   ├── audio_maker.py      # ElevenLabs TTS tool
│   ├── video_maker.py      # Veo 3.1 video generation
│   └── lipsync.py          # Sync API lipsync tool
└── orchestrator/            # Multi-agent orchestration
    └── ugc_orchestrator.py # Workflow orchestration
```

## 📋 Prerequisites

- Python 3.9+
- Node.js 18+ and npm (for frontend)
- PostgreSQL database (running locally or remotely)
- AWS S3 bucket with appropriate credentials
- Auth0 account for authentication
- API keys for:
  - OpenAI API (for GPT-4o agents and script generation)
  - Google Gemini API (for image generation via google-genai)
  - AIML API (for Veo 3.1 video generation)
  - ElevenLabs API (for text-to-speech audio)
  - LangSmith (for tracing and observability)
  - Optional: LIPSYNC_API_KEY (for lipsync feature)

## 🚀 Local Setup

### Backend Setup

#### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

#### 2. Configure Backend Environment Variables

Create a `.env` file in the `app/` directory:

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/ugc_db

# AWS S3
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
S3_BUCKET_NAME=your-bucket-name
S3_FOLDER_PREFIX=UGC_Agent

# AI/ML APIs
OPENAI_API_KEY=your_openai_key
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
AIML_API_KEY=your_aiml_api_key
GEMINI_API_KEY=your_gemini_api_key
ELEVENLABS_API_KEY=your_elevenlabs_key

# LangSmith (for observability)
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=ugc-orchestrator

# Auth0 (for authentication)
AUTH0_DOMAIN=your-auth0-domain.auth0.com
AUTH0_AUDIENCE=your-api-audience

# CORS Configuration
CORS_ALLOWED_ORIGINS=http://localhost:5173,https://app.example.com

# Optional: Lipsync API
LIPSYNC_API_KEY=your_lipsync_key
```

#### 3. Initialize Database

Run the migration scripts to set up database tables:

```bash
# First, run the tenant isolation migration
python migrations/add_tenant_isolation_migration.py

# Then, run the column migration (if needed)
python migrations/add_columns_migration.py
```

Or initialize tables automatically on first run (the app will create them if they don't exist).

#### 4. Start the Backend Server

```bash
# Using uvicorn directly
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Or using Python module
python -m app.main
```

The backend will start on `http://localhost:8000`

### Frontend Setup

#### 1. Install Frontend Dependencies

```bash
cd frontend
npm install
```

#### 2. Configure Frontend Environment Variables

Create a `.env` file in the `frontend/` directory:

```env
VITE_API_BASE_URL=http://localhost:8000
```

#### 3. Start the Frontend Development Server

```bash
npm run dev
```

The frontend will start on `http://localhost:5173`

## 🧪 Local Testing

### 1. Health Check

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "online",
  "service": "UGC Orchestrator API with DB & S3",
  "version": "2.0.0",
  "database": "PostgreSQL",
  "storage": "AWS S3"
}
```

### 2. Brand Sync (Required First Step)

Before generating any content, sync your brand context:

```bash
curl -X POST http://localhost:8000/v1/brand/sync \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_AUTH0_TOKEN" \
  -d '{
    "industry": "skincare",
    "audience": "Gen Z women",
    "vibe": "authentic and relatable"
  }'
```

**Note:** All endpoints require authentication with a valid Auth0 JWT token in the `Authorization` header.

Response includes:
- `conversation_id`: Use this for subsequent requests
- `kai_response`: Natural language confirmation from Kai
- `trace_url`: LangSmith trace link (if enabled)

### 3. Generate UGC Images

Upload product image and select an avatar to generate 4 UGC variants:

```bash
curl -X POST http://localhost:8000/v1/ugc/upload \
  -H "Authorization: Bearer YOUR_AUTH0_TOKEN" \
  -F "message=Generate UGC images showing the product in use" \
  -F "product_image=@/path/to/product.jpg" \
  -F "avatar_id=1" \
  -F "conversation_id=your-conversation-id-from-brand-sync"
```

Response includes:
- `generated_images`: Array of 4 S3 URLs for generated images
- `assistant_message`: Response from Kai
- `steps`: Array of processing steps
- `trace_url`: LangSmith trace link

### 4. Generate Script, Audio & Video

Use one of the generated images to create a complete video:

```bash
curl -X POST http://localhost:8000/v1/ugc/script \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_AUTH0_TOKEN" \
  -d '{
    "ugc_image_path": "https://teems-agents.s3.../generated_image_1.png",
    "product_name": "Glow Serum",
    "avatar_id": 1,
    "tone": "energetic and authentic",
    "platform": "Instagram",
    "conversation_id": "your-conversation-id"
  }'
```

Response includes:
- `script`: Video script text
- `dialogue`: Dialogue text for audio
- `audio_url`: S3 URL of generated audio
- `video_url`: URL of generated video
- `voice_used`: Voice name used for audio

### 5. Get Conversation History

Retrieve all messages and assets for a conversation:

```bash
curl http://localhost:8000/v1/conversations/your-conversation-id \
  -H "Authorization: Bearer YOUR_AUTH0_TOKEN"
```

### 6. List Conversations

List all conversations for your tenant:

```bash
curl http://localhost:8000/v1/conversations?limit=20&offset=0 \
  -H "Authorization: Bearer YOUR_AUTH0_TOKEN"
```

### 7. Delete Conversation

```bash
curl -X DELETE http://localhost:8000/v1/conversations/your-conversation-id \
  -H "Authorization: Bearer YOUR_AUTH0_TOKEN"
```

## 📚 API Endpoints

All endpoints require authentication with a valid Auth0 JWT token in the `Authorization: Bearer <token>` header.

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/health` | Health check | No |
| `GET` | `/v1/avatars/list` | List available avatars | Yes |
| `POST` | `/v1/brand/sync` | Lock brand context | Yes |
| `POST` | `/v1/ugc/upload` | Upload images & generate UGC variants | Yes |
| `POST` | `/v1/ugc/script` | Generate script, audio & video | Yes |
| `GET` | `/v1/conversations` | List conversations (with pagination) | Yes |
| `GET` | `/v1/conversations/{id}` | Get conversation history | Yes |
| `DELETE` | `/v1/conversations/{id}` | Delete conversation | Yes |

## 🔐 Authentication & Authorization

The service uses Auth0 for authentication and implements tenant isolation for all data operations.

### Authentication

All API endpoints (except `/health`) require a valid Auth0 JWT token:

```bash
Authorization: Bearer <your-auth0-token>
```

The token must include:
- `tenant_id` claim (custom claim: `https://teems.ai/tenant_id` or `tenant_id`)
- Valid audience matching `AUTH0_AUDIENCE`
- Valid issuer matching Auth0 domain

### Tenant Isolation

All data operations are scoped to the authenticated user's tenant:
- Conversations are isolated by `tenant_id`
- Assets are isolated by `tenant_id`
- Users can only access their own tenant's data
- Ownership verification is enforced on all operations

### Getting an Auth0 Token

Use your Auth0 application credentials to obtain a token:

```bash
curl -X POST https://YOUR_AUTH0_DOMAIN/oauth/token \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "your-client-id",
    "client_secret": "your-client-secret",
    "audience": "your-api-audience",
    "grant_type": "client_credentials"
  }'
```

## 🔍 Observability

All agent workflows are traced with LangSmith. Each response includes a `trace_url` that links to:
- Agent execution traces
- Tool calls and results
- LLM interactions
- Performance metrics

View traces at: `https://smith.langchain.com`

## 🛠️ Development

### Running Tests

```bash
# Run database migration
python migrations/add_columns_migration.py

# Test S3 utilities
python -m app.services.s3_utils

# Test database helpers
python -m app.services.db_helpers

# Test lipsync agent
python app/test_lipsync_agent.py

# Test lipsync direct
python app/test_lipsync_direct.py
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### Code Structure

- **Frontend** (`frontend/src/`): React + TypeScript UI with Tailwind CSS
  - `components/`: React components (ChatInterface, AvatarGrid, AuthInput)
  - `services/`: API client and utilities
  - `types/`: TypeScript type definitions
- **Routes** (`app/api/routes/`): Handle HTTP requests, validate input, call services
- **Services** (`app/services/`): Business logic, database operations, S3 operations
- **Agents** (`app/agents/`): CrewAI agent definitions with tools and LLM configs
- **Tools** (`app/tools/`): CrewAI tools that wrap external APIs
  - `prompt_variator.py`: GPT-4o vision prompt generation
  - `banana_ugc.py`: Google Gemini image generation
  - `script_maker.py`: Script generation tool
  - `audio_maker.py`: ElevenLabs TTS tool
  - `video_maker.py`: Veo 3.1 video generation
  - `lipsync.py`: Sync API lipsync tool
- **Orchestrator** (`app/orchestrator/`): Multi-agent workflow coordination
- **Models** (`app/models/`): Pydantic schemas for request/response validation
- **Core** (`app/core/`): Database models, configuration, dependencies
- **Config** (`app/config/`): Avatar and voice configurations

### Adding New Features

1. **New Agent**: Add to `app/agents/` with proper imports
2. **New Tool**: Add to `app/tools/` following existing tool patterns
3. **New Endpoint**: Add route to `app/api/routes/` and register in `app/main.py`
4. **New Schema**: Add Pydantic model to `app/models/schemas.py`

## 🐛 Troubleshooting

### Database Connection Issues

```bash
# Verify PostgreSQL is running
psql -U your_user -d ugc_db -c "SELECT 1;"

# Check DATABASE_URL format
# Should be: postgresql+asyncpg://user:password@host:port/dbname
```

### S3 Upload Issues

```bash
# Verify AWS credentials
aws s3 ls s3://your-bucket-name

# Check bucket permissions
# Ensure bucket allows public-read for AI/ML API access
```

### Agent Execution Issues

- Check LangSmith traces for detailed error logs
- Verify `AIML_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, and `ELEVENLABS_API_KEY` are set correctly
- Ensure brand context is synced before image generation
- Check that uploaded images are accessible via S3 URLs

### Frontend Issues

```bash
# Clear node_modules and reinstall
cd frontend
rm -rf node_modules package-lock.json
npm install

# Check environment variables
cat .env

# Verify API connection
curl http://localhost:8000/health
```

## 📝 Notes

- **Full-Stack Application**: Backend (FastAPI) + Frontend (React + TypeScript)
- **Authentication Required**: All endpoints (except `/health`) require Auth0 authentication
- **Tenant Isolation**: All data is isolated by tenant_id - users can only access their tenant's data
- **Avatar-Based Generation**: Uses predefined avatars instead of person images for UGC generation
- **Brand Sync Required**: Brand context must be synced before generating images or scripts
- **S3-Only Storage**: All assets are stored in S3, no local temp files
- **Sequential Workflows**: Image generation uses 2-agent sequential workflow (prompt → image)
- **Parallel Generation**: 4 images are generated in parallel for efficiency
- **LangSmith Tracing**: Full observability enabled by default
- **API Versioning**: All endpoints use `/v1/` prefix for versioning
- **CORS**: Configured with specific allowed origins (no wildcards) for security
- **Google Gemini**: Used for image generation via google-genai SDK
- **ElevenLabs**: Used for text-to-speech audio generation
- **Veo 3.1**: Used for video generation via AIML API

## 🔗 Related Documentation

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [CrewAI Documentation](https://docs.crewai.com/)
- [LangSmith Documentation](https://docs.smith.langchain.com/)
