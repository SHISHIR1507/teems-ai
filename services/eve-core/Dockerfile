FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on

WORKDIR /app

COPY services/eve-core/requirements.txt ./
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

COPY --from=builder /opt/venv /opt/venv
COPY services/eve-core/src ./src
COPY services/eve-core/main.py main.py
COPY services/eve-core/README.md README.md
COPY platform ./platform
# .env file is optional - environment variables will be injected by ECS

EXPOSE 8080
CMD ["uvicorn", "eva_core.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
