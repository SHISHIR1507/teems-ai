# Social Media Agent Service

CrewAI-based agent service for multi-platform social media posting (TikTok, Facebook). Provides a chat-based interface and REST API to post videos, manage tokens, and track post history with full tenant isolation and Auth0 authentication.

## Features

- **Multi-Agent CrewAI System**: Social Media Specialist, TikTok Specialist, Facebook Specialist
- **TikTok & Facebook Posting**: Full TikTok and Facebook Graph API video posting
- **OAuth Token Management**: TikTok and Facebook OAuth code exchange, token refresh (TikTok)
- **Conversation Persistence**: Chat history stored per conversation
- **Tenant Isolation**: All data scoped by `tenant_id` from Auth0
- **Auth0 Authentication**: JWT verification with JWKS caching, `require_tenant` dependency

## Architecture

```
services/agents/social_media/
├── app/
│   ├── agents/           # CrewAI agents (specialist, tiktok, facebook)
│   ├── api/routes/       # FastAPI endpoints
│   ├── core/             # Config, database, dependencies, auth
│   ├── models/           # Pydantic schemas
│   ├── orchestrator/     # Multi-agent workflows
│   ├── services/         # Business logic (TikTok, Facebook, S3, db_helpers)
│   └── tools/            # CrewAI tools (tiktok, facebook, platform)
├── main.py               # Entry point
├── Dockerfile
└── requirements.txt
```

## Quickstart

```bash
cd services/agents/social_media
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
export PYTHONPATH=.
uvicorn app.main:app --reload --port 8000
```

## Environment Variables

### Required

- `DATABASE_URL` - PostgreSQL connection string (asyncpg format, e.g. `postgresql+asyncpg://user:pass@host:5432/db`)
- `AIML_API_KEY` - AIML API key for LLM
- `TIKTOK_CLIENT_KEY` - TikTok OAuth app client key
- `TIKTOK_CLIENT_SECRET` - TikTok OAuth app client secret
- `AUTH0_DOMAIN` - Auth0 tenant domain
- `AUTH0_AUDIENCE` - Auth0 API audience

### Optional

- `AIML_BASE_URL` - Default: `https://api.aimlapi.com/v1`
- `LLM_MODEL` - Default: `openai/gpt-4o`
- `OAUTH_REDIRECT_URI` - TikTok OAuth redirect URI (default: `https://teems-web-app.vercel.app/callback/tiktok`)
- `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_REDIRECT_URI` - For Facebook OAuth
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET_NAME`, `S3_FOLDER_PREFIX` - For S3 (video storage)
- `AUTH0_ALGORITHM` - Default: `RS256`
- `CORS_ALLOWED_ORIGINS` - Comma-separated additional CORS origins

## API Endpoints

All protected endpoints require `Authorization: Bearer <access_token>` and a JWT with `tenant_id` (e.g. `https://teems.ai/tenant_id` or `tenant_id` claim).

### Health
- `GET /health` - Health check

### Chat
- `POST /v1/chat` - Chat with AI assistant (posting, history, platform info). Body: `{ "message": "...", "conversation_id": "optional-uuid" }`

### Conversations
- `GET /v1/conversations` - List tenant conversations (`?limit=20&offset=0`)
- `GET /v1/conversations/{id}` - Get conversation with messages
- `DELETE /v1/conversations/{id}` - Delete conversation

### Posts
- `GET /v1/posts` - List tenant posts (`?platform=tiktok|facebook&limit=20&offset=0`)
- `GET /v1/posts/{id}` - Get post details
- `DELETE /v1/posts/{id}` - Delete post record

### Tokens
- `GET /v1/tokens` - List connected platforms
- `DELETE /v1/tokens/{platform}` - Revoke token (`platform`: `tiktok` or `facebook`)

### OAuth
- `POST /v1/oauth/tiktok/exchange` - Exchange TikTok authorization code. Body: `{ "code": "..." }`
- `POST /v1/oauth/facebook/exchange` - Exchange Facebook authorization code. Body: `{ "code": "..." }`

### TikTok
- `POST /v1/tiktok/tokens/add` - Add TikTok token. Body: `{ "access_token": "...", "refresh_token": "...", "platform_user_id": "..." }`
- `POST /v1/tiktok/post` - Post video. Body: `{ "video_url": "...", "caption": "...", "hashtags": [] }`
- `GET /v1/tiktok/posts` - List TikTok posts (`?limit=20`)

### Facebook
- `POST /v1/facebook/tokens/add` - Add Facebook token. Body: `{ "access_token": "...", "platform_user_id": "..." }`
- `POST /v1/facebook/post` - Post video. Body: `{ "video_url": "...", "caption": "...", "page_id": "optional" }`
- `GET /v1/facebook/posts` - List Facebook posts (`?limit=20`)

## Usage Examples

### Chat (requires Auth)

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"message": "Post this video https://example.com/video.mp4 to TikTok with caption Hello!", "conversation_id": "optional-uuid"}'
```

### OAuth TikTok Exchange (requires Auth)

```bash
curl -X POST http://localhost:8000/v1/oauth/tiktok/exchange \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"code": "authorization_code_from_tiktok"}'
```

### Post to TikTok (requires Auth)

```bash
curl -X POST http://localhost:8000/v1/tiktok/post \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"video_url": "https://example.com/video.mp4", "caption": "Check this out!", "hashtags": ["viral", "trending"]}'
```

## Database Models

- `Conversation` - Conversation metadata
- `Message` - Chat messages
- `UserToken` - Platform tokens per tenant (tenant_id, platform composite PK)
- `Post` - Posted content (tenant_id, platform, etc.)

## Agents

1. **Social Media Specialist** - Main agent; coordinates posting, history, connected platforms
2. **TikTok Specialist** - TikTok posting and history
3. **Facebook Specialist** - Facebook posting and history

## Tools

- TikTok: `post_to_tiktok`, `get_tiktok_posts`, `refresh_tiktok_token`
- Facebook: `post_to_facebook`, `get_facebook_posts`
- Platform: `get_user_posts`, `get_connected_platforms`

## Deployment

The service is containerized and can be deployed to ECS or Kubernetes. Ensure `DATABASE_URL`, Auth0, and TikTok/Facebook OAuth env vars are set.

## License

Proprietary - Teems AI
