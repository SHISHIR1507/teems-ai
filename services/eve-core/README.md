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
- `AUTH0_DOMAIN` – your Auth0 domain (e.g. `your-tenant.us.auth0.com`).
- `AUTH0_AUDIENCE` – the API audience configured in Auth0.
- `AUTH0_ALGORITHM` – JWT algorithm, usually `RS256`.

## API Surface

- `GET /health` – readiness/liveness probe (no auth).
- `POST /v1/rag/ingest/text` – authenticated; JSON body `{ text, title?, metadata? }`. The `tenant_id` is derived from the authenticated user's token.
- `POST /v1/rag/ingest/file` – authenticated; multipart upload (optional `title/metadata`, file field `file`). The `tenant_id` is derived from the authenticated user's token.
- `POST /v1/rag/chat` – authenticated; JSON body `{ query, chat_history?, llm_provider?, llm_model?, top_k? }`. The `tenant_id` is derived from the authenticated user's token.

All RAG endpoints require an `Authorization: Bearer <access_token>` header containing a valid Auth0 access token. The token must include a `tenant_id` claim (preferably in the `https://teems.ai/tenant_id` namespace); Eve Core uses this claim to scope all document storage and retrieval.

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

1. Obtain an Auth0 access token that includes a `tenant_id` claim.
2. Ingest a sample document via `/v1/rag/ingest/text` with the `Authorization` header set.
3. Hit `/v1/rag/chat` with `{ "query": "..." }` and the same `Authorization` header.
4. Optionally set `llm_provider` to `gemini` or `openai` and override `llm_model`.

The service will retrieve the top chunks for the authenticated user's tenant from Postgres, feed them plus chat history into the requested model, and return the answer with references.
