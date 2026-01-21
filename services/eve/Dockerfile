FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on

WORKDIR /app

COPY services/eve/requirements.txt ./
RUN python -m venv /opt/venv && \
    . /opt/venv/bin/activate && \
    pip install --upgrade pip && \
    pip install -r requirements.txt

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app/src"

WORKDIR /app

# Add Node.js + npm for MCP servers that rely on `npx` (tavily-mcp, server-postgres)
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm ca-certificates \
  && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
COPY services/eve/src ./src
COPY services/eve/agent ./agent
COPY services/eve/mcp ./mcp
COPY services/eve/meeting_rag ./meeting_rag
COPY services/eve/main.py ./
COPY services/eve/migrate_db.py ./
COPY platform/shared_libs ./platform/shared_libs

EXPOSE 5000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
