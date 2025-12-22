# UGC Video Creator Service

FastAPI microservice for generating User-Generated Content (UGC) videos using CrewAI multi-agent workflows. Supports three types of UGC content:

1. **Physical Product & Person**: Combines person image with product image
2. **Digital Product & Person**: Combines person image with app/website screenshots (shown in device frames)
3. **Service & Person**: Person talking about a service with optional logo placement

## Features

- **Auto-detection**: Automatically detects UGC type based on uploaded files
- **Multi-agent Workflows**: Uses CrewAI for orchestrated agent execution
- **Image Generation**: Generates 4 diverse UGC image variants using Banana UGC tool
- **Video Generation**: Creates 8-second videos from images using Veo-3.1
- **S3 Storage**: All generated artifacts stored in S3 with presigned URLs
- **Conversation Management**: Tracks conversation history and generated artifacts
- **Auth0 Integration**: Secure authentication and tenant isolation

## Architecture

The service uses a 2-agent sequential workflow pattern:

### Image Generation Workflow
1. **Prompt Variator Agent**: Generates 4 diverse prompts from base intent
2. **Image Generator Agent**: Generates 4 images (one per prompt) using Banana UGC tool

### Video Generation Workflow
1. **Script Generator Agent**: Creates 8-second video script optimized for Veo-3
2. **Video Generator Agent**: Generates video from image + script using Veo-3.1

## Quickstart

```bash
cd services/agents/ugc_video
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill values
export PYTHONPATH=src
uvicorn ugc_video.app:create_app --factory --reload --port 8080
```

## Required Environment Variables

- `DATABASE_URL` – PostgreSQL connection string (async SQLAlchemy format)
- `AUTH0_DOMAIN` – Auth0 domain (e.g., `your-tenant.us.auth0.com`)
- `AUTH0_AUDIENCE` – Auth0 API audience
- `AUTH0_ALGORITHM` – JWT algorithm (default: `RS256`)
- `AIML_API_KEY` – AIML API key for accessing OpenAI/Gemini models
- `AIML_BASE_URL` – Base URL for AIML API (default: `https://api.aimlapi.com/v1`)
- `AWS_ACCESS_KEY_ID` – AWS access key for S3
- `AWS_SECRET_ACCESS_KEY` – AWS secret key for S3
- `AWS_REGION` – AWS region (default: `us-east-1`)
- `S3_BUCKET_NAME` – S3 bucket name for storing artifacts
- `AGENT_MANAGER_BASE_URL` – Base URL for agent-manager service (optional)
- `LANGCHAIN_TRACING_V2` – Enable LangSmith tracing (default: `false`)
- `LANGCHAIN_PROJECT` – LangSmith project name (default: `ugc-video-creator`)
- `LANGCHAIN_API_KEY` – LangSmith API key (optional)

## API Endpoints

### POST `/api/v1/chat`
Main chat endpoint for UGC generation.

**Request (multipart/form-data):**
- `message` (string, required): User's message/intent
- `person_image` (file, optional): Person image file
- `product_image` (file, optional): Product image (for physical products)
- `screenshot` (file, optional): Screenshot (for digital products)
- `logo` (file, optional): Logo image (for services)
- `conversation_id` (string, optional): Existing conversation ID

**Response:**
```json
{
  "conversation_id": "uuid",
  "assistant_message": "string",
  "ugc_type": "physical_product|digital_product|service",
  "generated_images": ["s3_url_1", "s3_url_2", ...],
  "status": "completed",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### POST `/api/v1/chat/{conversation_id}/generate-video`
Generate video from a selected image.

**Request (JSON):**
```json
{
  "image_id": "uuid",
  "product_name": "string",
  "tone": "energetic and authentic",
  "platform": "Instagram"
}
```

**Response:**
```json
{
  "conversation_id": "uuid",
  "script": "video script text",
  "video_url": "s3_presigned_url",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### GET `/api/v1/conversations/{conversation_id}`
Get conversation history with artifacts.

### GET `/api/v1/conversations`
List conversations for authenticated user.

### GET `/health`
Health check endpoint.

## Database Schema

### Conversations
- `id` (UUID)
- `tenant_id` (String, indexed)
- `user_id` (String, indexed)
- `ugc_type` (Enum: physical_product, digital_product, service)
- `status` (Enum: active, completed, archived)
- `metadata` (JSON)
- `created_at`, `updated_at` (timestamps)

### Messages
- `id` (UUID)
- `conversation_id` (FK to Conversation)
- `role` (Enum: user, assistant, system)
- `content` (Text)
- `metadata` (JSON)
- `created_at` (timestamp)

### Artifacts
- `id` (UUID)
- `conversation_id` (FK to Conversation)
- `artifact_type` (Enum: image, video, script)
- `s3_key` (String)
- `s3_url` (String, presigned URL)
- `metadata` (JSON)
- `created_at` (timestamp)

## UGC Type Detection

The service automatically detects UGC type based on uploaded files:

- **Physical Product**: Both `person_image` and `product_image` uploaded
- **Digital Product**: `person_image` + `screenshot` uploaded, or message contains digital keywords
- **Service**: Only `person_image` with service keywords, or `logo` provided

## Integration with Agent Manager

The service can be integrated with the agent-manager service:

1. Register the UGC Video Creator agent in agent-manager database
2. When agent is run via `POST /api/agents/{id}/run`, agent-manager calls UGC service endpoints
3. UGC service processes the request and returns results
4. Agent-manager updates AgentRun status

## Development

### Running Tests
```bash
pytest tests/
```

### Local Development
```bash
# Start PostgreSQL and ensure database exists
# Set environment variables in .env
uvicorn ugc_video.app:create_app --factory --reload --port 8080
```

### Docker Build
```bash
docker build -f services/agents/ugc_video/Dockerfile -t ugc-video-creator .
```

## Deployment

The service follows the same deployment pattern as other services:

1. Build Docker image
2. Push to ECR
3. Deploy using ECS Fargate stack (see `infra/ecs-ugc-video-stack.yaml`)
4. Configure environment variables in ECS task definition

## Notes

- All generated images and videos are stored in S3
- Presigned URLs are generated for temporary access (1 hour expiration)
- Conversation history is persisted in PostgreSQL
- LangSmith tracing is optional but recommended for monitoring

