FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=on \
    PIP_DISABLE_PIP_VERSION_CHECK=on

WORKDIR /app

COPY services/eve-core/requirements.txt ./
RUN python -m venv /opt/venv && \
    . /opt/venv/bin/activate && \
    pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    find /opt/venv -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true && \
    find /opt/venv -type f -name "*.pyc" -delete 2>/dev/null || true

FROM python:3.11-slim

# Install system dependencies required by PyMuPDF, Pillow, OCR, and related libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

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
