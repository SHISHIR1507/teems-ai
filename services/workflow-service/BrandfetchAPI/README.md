# Brandfetch Workflow Service

Production-ready FastAPI microservice that fetches brand metadata from Brandfetch, caches it in PostgreSQL, and exposes workflow-friendly endpoints.

## Features

- Cleans user-provided URLs/domains before calling Brandfetch.
- Persists responses as JSON so downstream jobs can reuse them.
- Offers cache-first lookups with optional refresh to manage rate limits.
- Ships with Dockerfile and `.env` placeholders for rapid deployment.

## Quickstart

```bash
cd services/workflow-service/BrandfetchAPI
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env .env.local  # fill values inside .env.local
uvicorn app.main:app --reload --port 8095
```

Update `.env`/`.env.local` with:

- `BRANDFETCH_API_KEY` – API token from Brandfetch.
- `DATABASE_URL` – SQLAlchemy async connection string (e.g., `postgresql+asyncpg://user:pass@host:5432/db`).
- `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`, `AUTH0_ALGORITHM` – for JWT verification; tenant_id is read from the token.
- `REDIS_URL` – required for onboarding pubsub events.
- Optional overrides: `BRANDFETCH_ENDPOINT`, `REQUEST_TIMEOUT_SECONDS`, `CACHE_TTL_SECONDS`, `ONBOARDING_CHANNEL_PREFIX`, `CORS_ALLOWED_ORIGINS`.

## Endpoints

- `GET /health` – readiness probe.
- `POST /brands/fetch` – Auth required. Body `{ "url": "slack.com", "force_refresh": false, "conversation_id": "..." }`. Tenant/user derived from token. Emits Redis pubsub event on `onboarding:{tenant_id}` with `brandfetch.completed` and includes `conversation_id` (taken from `X-Conversation-Id` header if present, else body).
- `GET /brands/{domain}?refresh=false` – Auth required. Return cached record, optionally re-fetch from Brandfetch.
- `GET /brands?limit=20&offset=0` – Paginated list of cached brands.

All responses include normalized domain plus the full JSON payload we received from Brandfetch.

## Docker

```bash
docker build -t brandfetch-service .
docker run --env-file .env -p 8095:8080 brandfetch-service
```

## Deployment Notes

- ECS/EKS/Lambda containers need Brandfetch API, PostgreSQL, Redis (for events).
- The app auto-creates its table on startup, but consider promoting to migrations (Alembic) in shared environments.
- Cloud monitoring can target `/health`; logs go to stdout so they integrate with any log collector.

### Browser access / CORS
This service uses env-driven CORS via `CORS_ALLOWED_ORIGINS` (comma/space separated). Local defaults for common localhost ports are always allowed.

