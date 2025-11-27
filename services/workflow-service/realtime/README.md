# Realtime Workflow Service

Simple FastAPI service that exposes a WebSocket endpoint so frontend clients can create lightweight jobs and receive completion notifications instantly.

## Features

- Single `/ws` WebSocket entrypoint (`ws://.../ws`).
- Clients send `{ "action": "create_job", "payload": { ... } }`.
- Service replies with `JOB_ACCEPTED` immediately and `JOB_COMPLETED` once the async task finishes.
- Optional REST `GET /jobs/{job_id}` to poll status after reconnects.

## Quickstart

```bash
cd services/workflow-service/realtime
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env .env.local  # fill values if you need overrides
uvicorn app.main:app --reload --port 8096
```

### Environment Variables

| Key | Description |
| --- | --- |
| `DEFAULT_JOB_DURATION_SECONDS` | Fake processing delay per job (default 3). |
| `MAX_CONNECTIONS` | Optional hard cap for simultaneous sockets (default 500). |
| `LOG_LEVEL` | `debug`/`info` etc. |

## WebSocket Contract

1. Client connects and optionally sends `{"action":"ping"}` to keep-alive.
2. To create work: `{"action":"create_job","payload":{"data":"hello","duration":5}}`.
3. Server responds:
   - `{"type":"JOB_ACCEPTED","job_id":"...","status":"pending"}`
   - Later: `{"type":"JOB_COMPLETED","job_id":"...","status":"completed","result":{...}}`
   - Errors bubble as `{"type":"JOB_ERROR","job_id":"...","error":"..."}`.

If the socket drops, hit `GET /jobs/{job_id}` to read stored status/results and optionally fire a new websocket connection.

## Docker

```bash
docker build -t realtime-workflow .
docker run -p 8096:8080 --env-file .env realtime-workflow
```

Deploy behind your gateway or ALB; health checks target `GET /health`.

