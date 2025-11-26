from __future__ import annotations

import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..models.document import Document, DocumentChunk
from ..schemas.rag import (
    ChatRequest,
    ChatResponse,
    DocumentIngestRequest,
    DocumentIngestResponse,
    SourceChunk,
)
from .chunker import chunk_text
from .embedding import EmbeddingProvider
from .llm import LLMFactory


class RAGService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        embedder: EmbeddingProvider,
        llm_factory: LLMFactory,
    ) -> None:
        self.session = session
        self.settings = settings
        self.embedder = embedder
        self.llm_factory = llm_factory

    async def ingest_text(self, payload: DocumentIngestRequest) -> DocumentIngestResponse:
        chunks = chunk_text(payload.text, self.settings.chunk_size, self.settings.chunk_overlap)
        embeddings = await self.embedder.embed(chunks)

        document = Document(
            tenant_id=payload.tenant_id,
            title=payload.title,
            metadata=payload.metadata,
        )
        self.session.add(document)
        await self.session.flush()

        chunk_models: list[DocumentChunk] = []
        for idx, (chunk_text_value, vector) in enumerate(zip(chunks, embeddings, strict=False)):
            chunk_models.append(
                DocumentChunk(
                    document_id=document.id,
                    tenant_id=payload.tenant_id,
                    chunk_index=idx,
                    content=chunk_text_value,
                    metadata={"source": "text_ingest", **(payload.metadata or {})},
                    embedding=vector,
                )
            )

        self.session.add_all(chunk_models)
        await self.session.commit()
        return DocumentIngestResponse(document_id=str(document.id), chunks_created=len(chunk_models))

    async def chat(self, request: ChatRequest) -> ChatResponse:
        query_vector = await self.embedder.embed_one(request.query)
        top_k = request.top_k or self.settings.top_k

        stmt = (
            select(
                DocumentChunk,
                Document,
                (1 - DocumentChunk.embedding.cosine_distance(query_vector)).label("score"),
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(DocumentChunk.tenant_id == request.tenant_id)
            .order_by(DocumentChunk.embedding.cosine_distance(query_vector))
            .limit(top_k)
        )

        rows = (await self.session.execute(stmt)).all()
        if not rows:
            return ChatResponse(
                answer="I could not find relevant context for your question.",
                sources=[],
                provider=request.llm_provider or self.settings.default_llm_provider,
                model=request.llm_model or self.settings.default_llm_model,
                generated_at=self._now(),
                latency_ms=0,
            )

        context_blocks = []
        sources: list[SourceChunk] = []
        for chunk, document, score in rows:
            context_blocks.append(
                f"Document: {document.title or document.id}\nChunk: {chunk.content}"
            )
            sources.append(
                SourceChunk(
                    chunk_id=str(chunk.id),
                    document_id=str(document.id),
                    title=document.title,
                    content=chunk.content,
                    score=float(score or 0),
                    metadata=chunk.metadata,
                )
            )

        system_prompt = (
            "You are a helpful assistant. Answer using ONLY the provided context. "
            "If the context does not contain the answer, say you do not know."
        )

        messages = [{"role": "system", "content": system_prompt}]
        for message in request.chat_history:
            messages.append({"role": message.role, "content": message.content})

        messages.append(
            {
                "role": "system",
                "content": "Context:\n" + "\n\n".join(context_blocks),
            }
        )
        messages.append({"role": "user", "content": request.query})

        provider = request.llm_provider or self.settings.default_llm_provider
        model = request.llm_model or self.settings.default_llm_model
        llm_client = self.llm_factory.get_client(provider)

        start = time.perf_counter()
        answer = await llm_client.generate(messages, model=model)
        latency_ms = int((time.perf_counter() - start) * 1000)

        return ChatResponse(
            answer=answer,
            sources=sources,
            provider=provider,
            model=model,
            latency_ms=latency_ms,
            generated_at=self._now(),
        )

    @staticmethod
    def _now():
        from datetime import datetime, timezone

        return datetime.now(timezone.utc)

