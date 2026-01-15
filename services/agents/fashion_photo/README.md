# Fashion Photo Agent Service

FastAPI microservice that provides an AI-powered fashion photography assistant using CrewAI and image generation APIs. Guides users through a multi-stage workflow to create AI-generated fashion images.

## Features

- **Multi-Stage Workflow**: Avatar selection → Apparel upload → Scene selection → Image generation
- **AI-Powered Chat**: Conversational interface powered by CrewAI with GPT-4o
- **Image Generation**: Parallel generation of fashion images from multiple angles (Front, Back, Side, Motion, Close Up)
- **Vision Analysis**: GPT-4o Vision for analyzing apparel style and vibes
- **Session Management**: In-memory session tracking for workflow state
- **S3 Integration**: Automatic upload and storage of user-uploaded and AI-generated images
- **LangSmith Integration**: Tracing and feedback collection for LLM operations

## 🏗️ Architecture

The service follows FastAPI best practices with a clean, modular structure:

```
app/
├── core/                   # Core application components
│   └── config.py          # Environment configuration & settings
├── schemas/                # Pydantic request/response models
│   ├── request.py         # API request schemas
│   └── response.py        # API response schemas
├── services/               # Business logic layer
│   ├── session_service.py # Session state management
│   ├── s3_service.py      # S3 upload utilities
│   ├── image_generation.py # Image generation logic & tools
│   ├── vision_service.py  # Vision analysis service
│   └── agent_service.py   # CrewAI agent orchestration
└── routers/                # API endpoint handlers
    ├── health.py          # Health check endpoint
    ├── avatar.py          # Avatar selection endpoints
    ├── upload.py          # File upload endpoints
    ├── chat.py            # Chat/conversation endpoint
    └── feedback.py        # Feedback endpoint
```

## 📋 Prerequisites

- Python 3.11+
- AWS S3 bucket configured
- API keys for:
  - AIML API (for image generation and vision analysis)
  - LangSmith API (optional, for tracing)

## 🚀 Local Setup

### 1. Install Dependencies

```bash
cd services/agents/fashion_photo
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the `fashion_photo` directory:

```env
# LangSmith Configuration
LANGSMITH_PROJECT=photographer_agent
LANGSMITH_API_KEY=your_langsmith_api_key
LANGCHAIN_TRACING_V2=true

# AWS Configuration
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=eu-north-1
S3_BUCKET_NAME=your_bucket_name

# API Keys
AIML_API_KEY=your_aiml_api_key
```

### 3. Start the Server

```bash
# From the fashion_photo directory
uvicorn main:app --reload --port 8000
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
  "status": "online",
  "service": "Fashion Photo Agent",
  "version": "1.0.0"
}
```

### 2. Select Avatar

```bash
curl -X POST http://localhost:8000/select_avatar \
  -F "session_id=test-session-123" \
  -F "avatar_url=https://example.com/avatar.png"
```

### 3. Upload Images

```bash
curl -X POST http://localhost:8000/upload \
  -F "session_id=test-session-123" \
  -F "type=apparel" \
  -F "files=@/path/to/image1.jpg" \
  -F "files=@/path/to/image2.jpg"
```

### 4. Chat with Agent

```bash
curl -X POST http://localhost:8000/chat \
  -F "session_id=test-session-123" \
  -F "message=Suggest some scenes for my fashion photos"
```

### 5. Submit Feedback

```bash
curl -X POST http://localhost:8000/feedback \
  -F "session_id=test-session-123" \
  -F "image_url=https://example.com/generated-image.png" \
  -F "score=1" \
  -F "run_id=optional-run-id"
```

## 📚 API Endpoints

### `GET /health`
Health check endpoint.

**Response:** Service status and version

---

### `GET /`
Serves the home page HTML (if `index.html` exists).

---

### `POST /select_avatar`
Select a preset avatar for a session.

**Form Parameters:**
- `session_id` (string, required): Session identifier
- `avatar_url` (string, required): URL of the selected avatar

**Response:** Success status and current workflow stage

---

### `POST /upload`
Upload avatar or apparel images.

**Form Parameters:**
- `session_id` (string, required): Session identifier
- `type` (string, required): Either `'avatar'` or `'apparel'`
- `files` (file[], required): One or more image files

**Response:** Uploaded URLs and updated workflow stage

---

### `POST /chat`
Main conversational endpoint with the AI agent.

**Form Parameters:**
- `session_id` (string, required): Session identifier
- `message` (string, optional): User's chat message

**Response:** Agent's response (may contain generated image URLs)

---

### `POST /feedback`
Submit user feedback (likes/dislikes) for generated images to LangSmith.

**Form Parameters:**
- `session_id` (string, required): Session identifier
- `image_url` (string, required): URL of the image being rated
- `score` (int, required): `1` for Like, `-1` for Dislike
- `run_id` (string, optional): LangSmith run ID to attach feedback to

**Response:** Feedback recording status

## 🔍 How It Works

1. **Workflow Stages**:
   - `AVATAR_SELECTION`: User selects or uploads an avatar
   - `APPAREL_UPLOAD`: User uploads apparel images
   - `SCENE_SELECTION`: Agent suggests creative scenes based on apparel
   - `GENERATION`: AI generates fashion images from multiple angles

2. **Image Generation**: 
   - Uses AIML API with `google/nano-banana-pro-edit` model
   - Generates 4 images per angle (Front, Back, Side, Motion, Close Up) in parallel
   - Automatically uploads generated images to S3 for permanent storage

3. **Agent Orchestration**:
   - CrewAI agent with GPT-4o as the Creative Director
   - Analyzes apparel using GPT-4o Vision
   - Suggests scenes and generates prompts for image generation

4. **Session Management**:
   - In-memory session storage (sessions do not persist across restarts)
   - Tracks avatars, apparel, generated images, and conversation history

## 🐛 Troubleshooting

### Missing Environment Variables

The service requires:
- `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` for S3 uploads
- `S3_BUCKET_NAME` for image storage
- `AIML_API_KEY` for image generation and vision analysis

### Image Generation Failures

1. Check AIML API key is valid
2. Verify image URLs are accessible
3. Check service logs for API error messages
4. Ensure sufficient credits on AIML API account

### S3 Upload Issues

1. Verify AWS credentials are correct
2. Check S3 bucket exists and is accessible
3. Ensure IAM permissions allow PutObject operations
4. Verify region matches bucket location

## 📝 Development Notes

- Sessions are stored in-memory and will be lost on service restart
- Generated images are automatically saved to S3 with permanent URLs
- The service supports parallel image generation for better performance
- LangSmith tracing is enabled by default when `LANGSMITH_API_KEY` is set

## 🔗 Related Services

- **AIML API**: Image generation and vision analysis
- **AWS S3**: Image storage
- **LangSmith**: LLM tracing and feedback collection
- **CrewAI**: Agent orchestration framework
