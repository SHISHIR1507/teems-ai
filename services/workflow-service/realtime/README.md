# Realtime Workflow Service

Simple FastAPI service that exposes a WebSocket endpoint so frontend clients can create lightweight jobs and receive completion notifications instantly.

## Features

- Single `/ws` WebSocket entrypoint (`ws://.../ws`).
- **First-message authentication** with Auth0 JWT tokens.
- Clients send `{ "action": "subscribe", "channels": [...] }` to receive Redis pub/sub messages.
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
| `AUTH0_DOMAIN` | Auth0 tenant domain (e.g., `teems.us.auth0.com`) |
| `AUTH0_AUDIENCE` | Auth0 API audience |
| `AUTH0_ALGORITHM` | JWT algorithm (default: `RS256`) |
| `REDIS_URL` | Redis connection URL for pub/sub |
| `MAX_CONNECTIONS` | Optional hard cap for simultaneous sockets (default 500). |
| `LOG_LEVEL` | `debug`/`info` etc. |

## WebSocket Authentication

The service uses **first-message authentication**. Clients must authenticate immediately after connecting.

### Authentication Flow

1. Client connects to `wss://host/ws`
2. Server accepts the connection
3. **Client MUST send auth message within 10 seconds:**
   ```json
   {"action": "auth", "token": "<JWT_ACCESS_TOKEN>"}
   ```
4. Server validates the JWT with Auth0 and checks for `tenant_id`
5. On success: `{"type": "AUTH_SUCCESS", "user": "...", "tenant_id": "..."}`
6. On failure: `{"type": "AUTH_FAILED", "error": "..."}` and connection closes

### Close Codes

| Code | Meaning |
|------|---------|
| 4001 | Auth timeout (no auth message within 10s) |
| 4002 | First message was not auth action |
| 4003 | Token missing in auth message |
| 4004 | Invalid token (Auth0 validation failed) |
| 4005 | User has no tenant_id assigned |
| 1011 | Internal server error |

## WebSocket Contract

1. Client connects and **sends auth first**: `{"action":"auth","token":"<JWT>"}`
2. On success, subscribe to channels: `{"action":"subscribe","channels":["channel1"]}`
3. Server responds:
   - `{"type":"AUTH_SUCCESS","user":"...","tenant_id":"..."}`
   - `{"type":"SUBSCRIBED","channels":[...]}`
   - Errors as `{"type":"ERROR","error":"..."}`
4. Ping/pong: `{"action":"ping"}` → `{"type":"PONG"}`

### JavaScript Client Example

```javascript
const ws = new WebSocket('wss://realtime.teems.ai/ws');

ws.onopen = () => {
  // First message MUST be auth
  ws.send(JSON.stringify({
    action: 'auth',
    token: accessToken  // JWT from Auth0
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'AUTH_SUCCESS') {
    console.log('Authenticated as', data.user);
    // Now can subscribe to channels
    ws.send(JSON.stringify({
      action: 'subscribe',
      channels: [`jobs:${data.tenant_id}`]
    }));
  } else if (data.type === 'AUTH_FAILED') {
    console.error('Auth failed:', data.error);
  } else if (data.type === 'SUBSCRIBED') {
    console.log('Subscribed to', data.channels);
  }
};
```

## Docker

```bash
docker build -t realtime-workflow .
docker run -p 8096:8080 --env-file .env realtime-workflow
```

Deploy behind your gateway or ALB; health checks target `GET /health`.

