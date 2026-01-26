# Fashion Photo Agent Service

CrewAI-based agent service for AI-powered fashion photography. This service provides a chat-based interface to create professional fashion images by combining user avatars with apparel photos, generating shots from multiple angles with AI-guided scene selection.

## Features

- **Multi-Agent CrewAI System**: Specialized agents for different tasks (Fashion Director, Scene Consultant, Image Generator)
- **Multi-Stage Workflow**: Avatar selection → Apparel upload → Scene selection → Image generation
- **Multi-Angle Generation**: Generates fashion images from 5 angles (Front, Back, Side, Motion, Close Up) with 4 variations each
- **Vision Analysis**: GPT-4o Vision for analyzing apparel style and vibes
- **S3 Storage**: All uploads and generated files stored in S3
- **Database Tracking**: Full session and image history with PostgreSQL
- **Authentication**: Auth0 JWT-based authentication with tenant isolation
- **LangSmith Integration**: Tracing and feedback collection for LLM operations

## Architecture

```
services/agents/fashion_photo/
├── app/
│   ├── agents/          # CrewAI agents
│   │   ├── fashion_director.py
│   │   ├── scene_consultant.py
│   │   └── image_generator_agent.py
│   ├── api/routes/       # FastAPI endpoints
│   │   ├── chat.py
│   │   ├── sessions.py
│   │   ├── avatar.py
│   │   ├── upload.py
│   │   ├── images.py
│   │   ├── scenes.py
│   │   ├── feedback.py
│   │   └── health.py
│   ├── core/             # Config, database, auth, dependencies
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── auth.py
│   │   ├── dependencies.py
│   │   └── logging.py
│   ├── models/           # Pydantic schemas
│   │   └── schemas.py
│   ├── orchestrator/     # Multi-agent workflows
│   │   └── fashion_orchestrator.py
│   ├── services/         # Business logic (S3, database helpers)
│   │   ├── db_helpers.py
│   │   └── s3_service.py
│   ├── tools/            # CrewAI tools
│   │   ├── image_tools.py
│   │   └── vision_tools.py
│   └── main.py           # FastAPI app
├── main.py               # Entry point
├── Dockerfile
├── README.md
└── requirements.txt
```

## Quickstart

```bash
cd services/agents/fashion_photo
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=app
uvicorn app.main:app --reload --port 8000
```

## Environment Variables

### Required

- `DATABASE_URL` - PostgreSQL connection string (asyncpg format)
- `AIML_API_KEY` - AIML API key for LLM and image generation
- `AUTH0_DOMAIN` - Auth0 domain
- `AUTH0_AUDIENCE` - Auth0 API audience
- `S3_BUCKET_NAME` - AWS S3 bucket name

### Optional

- `AIML_BASE_URL` - Default: `https://api.aimlapi.com/v1`
- `LLM_MODEL` - Default: `openai/gpt-4o`
- `AWS_ACCESS_KEY_ID` - AWS credentials (or use IAM role)
- `AWS_SECRET_ACCESS_KEY` - AWS credentials
- `AWS_REGION` - Default: `eu-north-1`
- `S3_FOLDER_PREFIX` - Default: `Fashion_Photo_Agent`
- `LANGCHAIN_TRACING_V2` - Default: `true`
- `LANGSMITH_PROJECT` - Default: `fashion_photo_agent`
- `LANGSMITH_API_KEY` - LangSmith API key (optional)
- `PRESET_AVATARS` - Comma-separated list of preset avatar URLs

## API Endpoints

### Sessions
- `POST /v1/sessions` - Create a new session
- `GET /v1/sessions/{id}` - Get session details
- `DELETE /v1/sessions/{id}` - Delete session
- `GET /v1/sessions` - List user's sessions

### Chat
- `POST /v1/chat` - Main chat endpoint with AI assistant

### Avatars
- `POST /v1/avatars` - Select or upload avatar
- `GET /v1/avatars` - List avatars for session

### Upload
- `POST /v1/upload` - Upload avatar or apparel images

### Images
- `POST /v1/images/generate` - Generate fashion images
- `GET /v1/images` - List generated images for session

### Scenes
- `POST /v1/scenes/suggest` - Get AI-suggested scenes

### Feedback
- `POST /v1/feedback` - Submit feedback for generated images

### Info
- `GET /health` - Health check

## Usage Examples

### Create Session

```bash
curl -X POST http://localhost:8000/v1/sessions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{}'
```

### Upload Avatar

```bash
curl -X POST http://localhost:8000/v1/upload \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "session_id=YOUR_SESSION_ID" \
  -F "upload_type=avatar" \
  -F "files=@avatar.png"
```

### Upload Apparel

```bash
curl -X POST http://localhost:8000/v1/upload \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "session_id=YOUR_SESSION_ID" \
  -F "upload_type=apparel" \
  -F "files=@apparel1.jpg" \
  -F "files=@apparel2.jpg"
```

### Chat with Agent

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "session_id": "YOUR_SESSION_ID",
    "message": "Suggest some scenes for my fashion photos"
  }'
```

### Generate Images

```bash
curl -X POST http://localhost:8000/v1/images/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "session_id": "YOUR_SESSION_ID",
    "scene_description": "Urban street style with natural lighting"
  }'
```

### Get Scene Suggestions

```bash
curl -X POST http://localhost:8000/v1/scenes/suggest \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "session_id": "YOUR_SESSION_ID"
  }'
```

## Database Models

- `FashionSession` - Session metadata and workflow state
- `Avatar` - Uploaded or selected avatars
- `Apparel` - Uploaded apparel images with vision analysis
- `GeneratedImage` - Generated fashion images
- `Message` - Conversation messages
- `Task` - Async task tracking

## S3 Storage Structure

```
s3://bucket-name/Fashion_Photo_Agent/
├── user_uploaded/        # User-uploaded avatars and apparel
├── ai_generated/         # AI-generated fashion images
```

## Agents

1. **Fashion Director** - Main orchestrator agent, guides workflow, coordinates tasks
2. **Scene Consultant** - Specialized for scene suggestions based on apparel analysis
3. **Image Generator** - Specialized for executing image generation

## Tools

- **Image Generation**: `ImageGenerationTool` - Generates fashion images from multiple angles
- **Vision Analysis**: `VisionAnalysisTool` - Analyzes apparel style and aesthetic

## Workflow Stages

1. **AVATAR_SELECTION** - User selects or uploads an avatar
2. **APPAREL_UPLOAD** - User uploads apparel images
3. **SCENE_SELECTION** - Agent suggests creative scenes based on apparel
4. **GENERATION** - AI generates fashion images from multiple angles

## Image Generation

- Generates 20 images total: 4 variations × 5 angles
- Angles: Front View, Back View, Side Profile, In Motion Walking Shot, Close Up
- Uses `google/nano-banana-pro-edit` model via AIML API
- Automatically uploads generated images to S3 for permanent storage
- Maintains identity preservation (facial features, apparel details)

## Deployment

The service is containerized and can be deployed to ECS or Kubernetes. See infrastructure configuration for deployment details.

## License

Proprietary - Teems AI
