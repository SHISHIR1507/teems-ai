# UGC Video Orchestrator Agent

An agentic workflow system for generating User-Generated Content (UGC) videos with AI. Uses CrewAI agents to orchestrate script generation, audio synthesis, image generation, and video creation with PostgreSQL persistence and AWS S3 storage.

## Features

- **Brand Sync**: Lock brand context (industry, audience, vibe) for consistent content generation
- **Image Generation**: Generate UGC images from person + product photos using Banana API
- **Script Generation**: AI-powered UGC script and dialogue creation
- **Audio Synthesis**: Text-to-speech with multiple avatar voices
- **Video Generation**: Image-to-video using Veo3.1 API
- **Database Persistence**: PostgreSQL with async SQLAlchemy
- **S3 Storage**: All assets stored in AWS S3 (no local temp files)
- **LangSmith Tracing**: Full observability of agent workflows

## Prerequisites

- Python 3.9+
- PostgreSQL database
- AWS S3 bucket
- API keys for:
  - OpenAI (for agents)
  - Banana API (for image generation)
  - AIML API (for audio/video generation)
  - LangSmith (for tracing)

## Setup

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Configure environment variables** - Create a `.env` file:
```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/ugc_db

# AWS S3
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
S3_BUCKET_NAME=your-bucket-name

# AI/ML APIs
OPENAI_API_KEY=your_openai_key
BANANA_API_KEY=your_banana_key
AIML_API_KEY=your_aiml_key

# LangSmith
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=ugc-orchestrator
```

3. **Initialize database** - Run the migration:
```bash
python add_columns_migration.py
```

4. **Start the server**:
```bash
python server_with_db.py
```

Server runs on `http://localhost:8000`

## API Endpoints

### Health Check
```
GET /health
```

### Brand Sync
```
POST /orchestrator/brand-sync
{
  "industry": "skincare",
  "audience": "Gen Z women",
  "vibe": "authentic and relatable"
}
```

### Generate UGC Images
```
POST /chat/ugc/upload
- message: "Generate UGC images"
- person_image: file
- product_image: file
- conversation_id: optional
```

### Generate Script + Audio + Video
```
POST /chat/ugc/script
{
  "ugc_image_path": "s3_url_or_path",
  "product_name": "Glow Serum",
  "avatar_id": 1,
  "tone": "energetic and authentic",
  "platform": "Instagram"
}
```

### Get Conversation History
```
GET /conversation/{conversation_id}
```

## Architecture

- **FastAPI**: REST API server
- **CrewAI**: Multi-agent orchestration
- **SQLAlchemy**: Async database ORM
- **PostgreSQL**: Conversation and asset persistence
- **AWS S3**: Asset storage (images, audio, video)
- **LangSmith**: Agent tracing and observability

## Database Schema

- `conversations`: Brand context and metadata
- `messages`: Chat history
- `assets`: Generated images, audio, video URLs

## Development

The system uses a 2-agent workflow:
1. **Script Agent**: Generates dialogue and video scripts
2. **Audio/Video Agent**: Creates audio and video assets

All assets are uploaded to S3 with public-read access for AI/ML API consumption.
