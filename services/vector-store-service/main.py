from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import sys
from pathlib import Path

from .config import Settings, get_settings
from .database import get_session, init_engine, init_models
from .models import DocumentChunk
from .schemas import ChunkHit, QueryRequest, QueryResponse, UpsertRequest

# Locate shared libs for CORS helper
current_file = Path(__file__).resolve()
current_dir = current_file.parent
while current_dir != current_dir.parent:
    shared_libs_candidate = current_dir / "platform" / "shared_libs"
    if shared_libs_candidate.exists():
        shared_libs_dir = shared_libs_candidate
        break
    current_dir = current_dir.parent
else:
    shared_libs_dir = current_file.parent.parent.parent / "platform" / "shared_libs"

sys.path.insert(0, str(shared_libs_dir))
from pyshared import add_env_cors  # noqa: E402


def create_app() -> FastAPI:
    settings = get_settings()
    init_engine(settings)

    app = FastAPI(
        title="Vector Store Service",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    add_env_cors(app)

    @app.on_event("startup")
    async def startup() -> None:
        logger.info("Initializing vector store models")
        await init_models()

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/vectors/upsert", tags=["vectors"])
    async def upsert_vectors(
        payload: UpsertRequest,
        session: AsyncSession = Depends(get_session),
    ) -> dict[str, Any]:
        for chunk in payload.chunks:
            model = DocumentChunk(
                id=chunk.id,
                tenant_id=chunk.tenant_id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                meta_data=chunk.metadata,
                embedding=chunk.embedding,
            )
            session.merge(model)
        await session.commit()
        return {"inserted": len(payload.chunks)}

    @app.post("/vectors/query", response_model=QueryResponse, tags=["vectors"])
    async def query_vectors(
        payload: QueryRequest,
        session: AsyncSession = Depends(get_session),
        settings: Settings = Depends(get_settings),
    ) -> QueryResponse:
        stmt = (
            select(
                DocumentChunk,
                (1 - DocumentChunk.embedding.cosine_distance(payload.embedding)).label("score"),
            )
            .where(DocumentChunk.tenant_id == payload.tenant_id)
            .order_by(DocumentChunk.embedding.cosine_distance(payload.embedding))
            .limit(payload.top_k)
        )
        rows = (await session.execute(stmt)).all()
        hits = [
            ChunkHit(
                id=str(row[0].id),
                document_id=str(row[0].document_id),
                content=row[0].content,
                metadata=row[0].meta_data,
                score=float(row[1] or 0),
            )
            for row in rows
        ]
        return QueryResponse(hits=hits)

    return app


app = create_app()


