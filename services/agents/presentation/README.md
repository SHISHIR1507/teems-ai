# Presentation Agent Service

CrewAI-based agent service for SlideSpeak API integration. This service provides a chat-based interface to create, edit, and manage PowerPoint presentations using natural language.

## Features

- **Multi-Agent CrewAI System**: Specialized agents for different tasks (specialist, generator, editor, brand manager)
- **SlideSpeak API Integration**: Full access to SlideSpeak capabilities
- **S3 Storage**: All uploads and generated files stored in S3
- **Webhook Support**: Async task notifications from SlideSpeak
- **Brand Customization**: Manage logos, colors, and fonts
- **Database Tracking**: Full conversation and presentation history

## Architecture

```
services/agents/presentation/
├── app/
│   ├── agents/          # CrewAI agents
│   ├── api/routes/       # FastAPI endpoints
│   ├── core/             # Config, database, dependencies
│   ├── models/           # Pydantic schemas
│   ├── orchestrator/     # Multi-agent workflows
│   ├── services/         # Business logic (SlideSpeak, S3, webhooks)
│   └── tools/            # CrewAI tools
├── main.py               # Entry point
├── Dockerfile
└── requirements.txt
```

## Quickstart

```bash
cd services/agents/presentation
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=app
uvicorn app.main:app --reload --port 8000
```

## Environment Variables

### Required

- `SLIDESPEAK_API_KEY` - SlideSpeak API key
- `AIML_API_KEY` - AIML API key for LLM
- `DATABASE_URL` - PostgreSQL connection string (asyncpg format)

### Optional

- `SLIDESPEAK_BASE_URL` - Default: `https://api.slidespeak.co/api/v1/`
- `AIML_BASE_URL` - Default: `https://api.aimlapi.com/v1`
- `LLM_MODEL` - Default: `openai/gpt-4o`
- `AWS_ACCESS_KEY_ID` - AWS credentials (or use IAM role)
- `AWS_SECRET_ACCESS_KEY` - AWS credentials
- `AWS_REGION` - Default: `us-east-1`
- `S3_BUCKET_NAME` - Default: `teems-agents`
- `S3_FOLDER_PREFIX` - Default: `Presentation_Agent`
- `WEBHOOK_BASE_URL` - Your service URL for webhook registration

## API Endpoints

### Chat
- `POST /v1/chat` - Main chat endpoint

### Presentations
- `GET /v1/presentations` - List user's presentations
- `GET /v1/presentations/{id}` - Get presentation details
- `GET /v1/presentations/{id}/download` - Get presigned download URL
- `DELETE /v1/presentations/{id}` - Delete presentation

### Upload
- `POST /v1/upload` - Upload document (PDF, Word, etc.)

### Templates & Branding
- `GET /v1/templates` - List available templates
- `GET /v1/templates/branded` - List branded templates
- `POST /v1/brand/sync` - Sync brand settings
- `GET /v1/brand` - Get brand settings

### Tasks & Webhooks
- `GET /v1/tasks/{id}/status` - Check task status
- `POST /v1/webhooks/slidespeak` - Receive SlideSpeak webhooks
- `GET /v1/webhooks/subscribe` - Subscribe to webhooks

### Conversations
- `GET /v1/conversations/{id}` - Get conversation history
- `DELETE /v1/conversations/{id}` - Delete conversation

### Info
- `GET /v1/info/credits` - Get API credits
- `GET /health` - Health check

## Usage Examples

### Generate Presentation

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "message": "Create a 10-slide presentation about quantum computing with a professional tone"
  }'
```

### Upload Document

```bash
curl -X POST http://localhost:8000/v1/upload \
  -F "file=@document.pdf" \
  -F "user_id=1" \
  -F "conversation_id=optional-uuid"
```

### Check Task Status

```bash
curl http://localhost:8000/v1/tasks/{task_id}/status
```

## Database Models

- `Conversation` - Conversation metadata and brand context
- `Message` - Chat messages
- `Presentation` - Generated presentations
- `Document` - Uploaded documents
- `Task` - Async task tracking

## S3 Storage Structure

```
s3://teems-agents/Presentation_Agent/
├── uploads/{conversation_id}/     # User-uploaded documents
├── presentations/{conversation_id}/ # Generated presentations
└── brand_assets/logos/             # Brand logos
```

## Agents

1. **Presentation Specialist** - Main agent, understands requirements, coordinates tasks
2. **Presentation Generator** - Specialized for generation
3. **Presentation Editor** - Specialized for editing
4. **Brand Manager** - Manages brand customization

## Tools

- Generation: `generate_presentation_from_text`, `generate_presentation_from_document`, `generate_presentation_slide_by_slide`
- Editing: `edit_presentation`, `edit_slide`
- Documents: `upload_document_to_slidespeak`, `check_document_processing_status`
- Templates: `get_available_templates`, `get_branded_templates`
- Brand: `check_task_status`, `get_api_credits`, `get_presentation_download_url`

## Deployment

The service is containerized and can be deployed to ECS or Kubernetes. See infrastructure configuration for deployment details.

## License

Proprietary - Teems AI
