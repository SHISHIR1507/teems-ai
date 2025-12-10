# Agent Manager

FastAPI service that lists curated agents, exposes detail pages, and lets authenticated users assign agents to their tenant and queue runs. Uses Auth0 for identity; tenant/user are taken from the access token.

## Endpoints
- `GET /api/agents?page=1&size=20&category=` – list agents (paginated, optional category).
- `GET /api/agents/{id}` – fetch agent detail.
- `POST /api/agents` – create agent (admin use).
- `PUT /api/agents/{id}` – update agent (admin use).
- `POST /api/agents/{id}/assign` – assign agent to current tenant/user (id/tenant/user derived from token).
- `POST /api/agents/{id}/run` – queue a run record (tenant/user derived from token; stores input payload).
- `GET /health` – health probe.

All protected routes require `Authorization: Bearer <token>` with `tenant_id` claim (namespace `https://teems.ai/tenant_id` or `tenant_id`).

## Local dev
```bash
cd services/agent-manager
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn agent_manager.main:app --reload --port 8080
```
Env (see `.env.example` if present):
- `DATABASE_URL`
- `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`, `AUTH0_ALGORITHM` (RS256)
- Optional: `CORS_ALLOWED_ORIGINS` (comma/space-separated)

## Docker
```bash
docker build -t agent-manager .
docker run --env-file .env -p 8080:8080 agent-manager
```

## Before pushing to main / deploy
- Ensure DB reachable and `DATABASE_URL` set.
- Ensure Auth0 secrets set (shared GitHub secrets supported).
- Run smoke: `curl -H "Authorization: Bearer <token>" http://localhost:8080/api/agents`.
- Verify CORS origins via `CORS_ALLOWED_ORIGINS` if testing from a browser.

