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
- Optional overrides for timeouts/log levels.

## Endpoints

- `GET /health` – readiness probe.
- `POST /brands/fetch` – Fetch + cache brand info. Payload `{ "url": "slack.com", "force_refresh": false }`.
- `GET /brands/{domain}?refresh=false` – Return cached record, optionally re-fetch from Brandfetch.
- `GET /brands?limit=20&offset=0` – Paginated list of cached brands (for dashboards/workflows).

All responses include normalized domain plus the full JSON payload we received from Brandfetch.

## Docker

```bash
docker build -t brandfetch-service .
docker run --env-file .env -p 8095:8080 brandfetch-service
```

## Deployment Notes

- ECS/EKS/Lambda containers simply need access to the Brandfetch API and PostgreSQL.
- The app auto-creates its table on startup, but consider promoting to migrations (Alembic) in shared environments.
- Cloud monitoring can target `/health`; logs go to stdout so they integrate with any log collector.

