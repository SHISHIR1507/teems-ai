# Eve Core – RAG Chat Service

FastAPI service that ingests tenant documents, stores embeddings in Postgres + pgvector, and answers chat questions using retrieval augmented generation (RAG) with selectable LLM providers (OpenAI or Gemini).

## Features

- Text and file ingestion (PDF, DOCX, TXT) with automatic chunking.
- Embedding generation via OpenAI or Gemini; stored as vectors in Postgres.
- RAG chat endpoint that lets callers select which LLM/model to use per request.
- Health check and job-friendly responses including source metadata.
- Dockerfile and `.env` placeholders for easy deployment.

## Quickstart

```bash
cd services/eve-core
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env .env.local  # fill values
export PYTHONPATH=src
uvicorn eva_core.app:create_app --factory --reload --port 8080
```

### Required environment variables

- `DATABASE_URL` – async SQLAlchemy URL, e.g. `postgresql+asyncpg://user:pass@host:5432/eve_core`
- `VECTOR_DIMENSION` – embedding dimension (1536 for `text-embedding-3-small`).
- `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` – `openai` or `gemini`.
- `OPENAI_API_KEY` / `GEMINI_API_KEY` – whichever providers you plan to use.
- `DEFAULT_LLM_PROVIDER` / `DEFAULT_LLM_MODEL` – fallback chat model.

## API Surface

- `GET /health` – readiness/liveness probe.
- `POST /v1/rag/ingest/text` – body `{ tenant_id, text, title?, metadata? }`.
- `POST /v1/rag/ingest/file` – multipart upload (`tenant_id`, optional `title/metadata`, file field `file`).
- `POST /v1/rag/chat` – `{ tenant_id, query, chat_history?, llm_provider?, llm_model?, top_k? }`.

Chat responses include `answer`, `sources[]`, `provider`, `model`, and latency. Sources provide chunk content plus document metadata for UI citation.

## Database

Enable pgvector in your database:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Tables are created automatically on startup, but promote migrations (Alembic) for shared environments.

## Docker

```bash
docker build -t eve-core .
docker run --env-file .env -p 8080:8080 eve-core
```

## Testing the Chat Endpoint

1. Ingest a sample document via `/v1/rag/ingest/text`.
2. Hit `/v1/rag/chat` with `{ "tenant_id": "demo", "query": "..." }`.
3. Optionally set `llm_provider` to `gemini` or `openai` and override `llm_model`.

The service will retrieve the top chunks from Postgres, feed them plus chat history into the requested model, and stream the answer back with references.
