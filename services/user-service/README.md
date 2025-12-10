# User Service (Auth0)

FastAPI microservice that sits behind Auth0 and exposes user-facing endpoints (profile lookup, logout helper, config bootstrap) plus persisted user preferences for the Teems platform.

## Features

- Validates Auth0-issued JWT access tokens with cached JWKS.
- Injects Auth0 config so frontend clients can bootstrap without shipping secrets.
- Health endpoint for platform monitoring and readiness probes.
- Deployment-ready via Docker (see `Dockerfile`).

## Requirements

- Python 3.11+
- Auth0 tenant with an API configured for this backend.
- PostgreSQL/AWS resources if you extend the service beyond authentication.

## Setup

```bash
cd services/user-service
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env .env.local  # optional so you keep placeholders
```

Fill in `.env` with your Auth0 tenant details, PostgreSQL params, and AWS secrets metadata.

## Running locally

```bash
uvicorn Auth.main:app --reload --port ${API_PORT:-8080}
```

## Docker

```bash
docker build -t teems-user-service .
docker run --env-file .env -p 8080:8080 teems-user-service
```

The container uses the same environment variables defined in `.env`. Cloud deployments can mount secrets or inject them via your orchestration tool of choice.

## Testing tokens

- Use Auth0's API explorer or Postman with a SPA/regular web app client to obtain an access token for the configured audience (must contain `tenant_id` claim).
- Call `GET /auth/me` with `Authorization: Bearer <token>` and expect a JSON profile; tenant is derived from token.
- Preferences: `GET /user/preferences` and `PUT /user/preferences` (body `notification_frequency`, `notification_channels[]`). User is auto-created/updated on first call; tenant/user derived from token.

## Folder structure

- `Auth/app.py` – creates the FastAPI instance.
- `Auth/config.py` – Pydantic settings loader backed by `.env`.
- `Auth/services/auth0.py` – JWKS caching, JWT verification helpers.
- `Auth/dependencies.py` – FastAPI dependencies for injecting Auth0 client/user context.
- `Auth/routers/*.py` – HTTP endpoints grouped by concern.
- `Dockerfile` – container image definition.

Extend routers/services as you add more user-specific operations (profile persistence, permissions, etc.).

