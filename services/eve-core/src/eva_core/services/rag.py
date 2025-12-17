from __future__ import annotations

import time
import uuid
from typing import Any
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..events import EventPublisher
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

from .recommendations import recommend_actions
from .message_service import MessageService
from .query_rewriter import QueryRewriterService


class RAGService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        embedder: EmbeddingProvider,
        llm_factory: LLMFactory,
        publisher: EventPublisher,
        message_service: MessageService,  
        query_rewriter: QueryRewriterService,  
    ) -> None:
        self.session = session
        self.settings = settings
        self.embedder = embedder
        self.llm_factory = llm_factory
        self.publisher = publisher
        self.message_service = message_service
        self.query_rewriter = query_rewriter

    async def ingest_text(self, payload: DocumentIngestRequest) -> DocumentIngestResponse:
        chunks = chunk_text(payload.text, self.settings.chunk_size, self.settings.chunk_overlap)
        embeddings = await self.embedder.embed(chunks)

        document = Document(
            tenant_id=payload.tenant_id,
            title=payload.title,
            meta_data=payload.metadata,
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
                    meta_data={"source": "text_ingest", **(payload.metadata or {})},
                    embedding=vector,
                )
            )

        self.session.add_all(chunk_models)
        await self.session.commit()
        await self.publisher.publish(
            f"conversation:{payload.tenant_id}",
            {
                "type": "ingest.completed",
                "document_id": str(document.id),
                "chunks_created": len(chunk_models),
                "tenant_id": payload.tenant_id,
            },
        )
        return DocumentIngestResponse(document_id=str(document.id), chunks_created=len(chunk_models))

    async def chat(self, request: ChatRequest) -> ChatResponse:
        rewrite_result = await self.query_rewriter.rewrite_query(
            original_query=request.query,
            tenant_id=request.tenant_id,
            conversation_id=request.conversation_id,
            limit=3
        )
        
        transformed_query = rewrite_result["rewritten_query"]
        needs_internet = rewrite_result["needs_internet"]

        if not request.conversation_id or request.conversation_id == "string":
            conversation_id = str(uuid.uuid4())
            print(f"Generated new conversation_id: {conversation_id}")

        else:
            conversation_id = request.conversation_id
            print(f"Using provided conversation_id: {conversation_id}")

        
        print(f"DEBUG: Will create conversation_id = {conversation_id}")
        print(f"DEBUG: tenant_id from request = {request.tenant_id}")
    
        from ..models.conversation import Conversation
        from datetime import datetime
        conv_stmt = select(Conversation).where(Conversation.id == conversation_id)
        result = await self.session.execute(conv_stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"Conversation already exists: {conversation_id}")
        else:
            print(f"Creating new conversation: {conversation_id}")
            
            # Create conversation record first
            conversation = Conversation(
                id=conversation_id,
                tenant_id=request.tenant_id,
                status="active",
                created_at=datetime.utcnow()
            )
            self.session.add(conversation)
            try:
                await self.session.flush()
                print(f"Conversation flushed to DB")
            except Exception as e:
                print(f"Flush failed: {e}")
                raise

        user_message = await self.message_service.save_message(
            tenant_id=request.tenant_id,
            conversation_id=conversation_id,
            role="user",
            content=request.query,  # Original query
            rewritten_content=transformed_query,  # Transformed query
            provider_metadata={  # Save needs_internet flag
                "needs_internet": needs_internet,
                "rewrite_info": {
                    "original_query": request.query[:100] if request.query else "",
                    "transformed_query": transformed_query[:100] if transformed_query else "",
                }
            }
        )

        query_vector = await self.embedder.embed_one(transformed_query)
        top_k = request.top_k or self.settings.top_k

        rag_stmt = (
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

        rows = (await self.session.execute(rag_stmt)).all()
        
        #if no relevant context found
        if not rows:
            recommendations = recommend_actions(transformed_query, k=3, threshold=0.25)
            response = ChatResponse(
                answer="I could not find relevant context for your question.",
                sources=[],
                provider=request.llm_provider or self.settings.default_llm_provider,
                model=request.llm_model or self.settings.default_llm_model,
                generated_at=self._now(),
                latency_ms=0,
                conversation_id=conversation_id,  
                needs_internet=needs_internet,
                recommendations=recommendations,
            )
            
            # Save assistant response
            await self._save_assistant_response(
                conversation_id=conversation_id,
                tenant_id=request.tenant_id,
                answer=response.answer
            )
            
            await self.session.commit()
            return response

        # ================== PROCESS RAG RESULTS ==================
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
                    metadata=chunk.meta_data,
                )
            )

        system_prompt = """
You are Eve — the Chief of Staff of the Teems.ai ecosystem.

You are the user’s calm, intelligent operational partner and the central orchestrator of their workspace.

Your responsibility is to understand the user’s business, coordinate Teem Mates (AI agents), maintain brand
consistency, reduce friction, and ensure high-quality output across every task.

Your role:

1. Understand what the user wants to accomplish.
2. Ask only essential questions (ideally 2–4), keeping cognitive load low.
3. Identify the right Teem Mate(s) and explain how they can help.
4. Organize the work, guide the user, and maintain clarity and structure.
5. Ensure consistency, quality, and smooth execution across the Teems.ai ecosystem.
6. Anticipate needs, reduce friction, and act one step ahead.

Available Teem Mates:

- VideoCreatorAI — creates short and long-form videos.
- ContentWriterAI — writes articles, scripts, blogs, captions.
- PostSchedulerAI — schedules posts across platforms.
- ResearcherAI — gathers structured insights, briefs, and summaries.
- DesignerAI — creates visuals (thumbnails, posters, graphics).

Tone Guidelines:

- Calm and reassuring
- Friendly but not overly casual
- Smart, structured, and highly competent
- Professional and confident
- Clear and concise
- Non-intrusive and premium
- Never salesy, never overwhelming
- Never condescending

Core Principles:

1. Learn first, act second.
2. Anticipate needs and take initiative.
3. Reduce friction in every interaction.
4. Ask only for essential information.
5. Prefer buttons and simple options over long text input.
6. Reassure users at hesitation points (especially around payment or complexity).
7. Avoid overwhelming the user with choices or explanations.
8. Ensure consistency across all Teem Mates.
9. Update the user only when necessary.
10. Operate like a real-world Chief of Staff — quietly effective, organized, and always one step ahead.

When responding:

- Be concise.
- Be structured.
- Guide the user smoothly.
- Recommend Teem Mates clearly, with brief explanations.
- Keep the user’s mental effort at a minimum.
""".strip()

        messages = [{"role": "system", "content": system_prompt}]
        for message in request.chat_history:
            messages.append({"role": message.role, "content": message.content})

        messages.append(
            {
                "role": "system",
                "content": "Context:\n" + "\n\n".join(context_blocks),
            }
        )
        messages.append({"role": "user", "content": transformed_query})

        provider = request.llm_provider or self.settings.default_llm_provider
        model = request.llm_model or self.settings.default_llm_model
        llm_client = self.llm_factory.get_client(provider)

        start = time.perf_counter()
        answer = await llm_client.generate(messages, model=model)
        latency_ms = int((time.perf_counter() - start) * 1000)

        recommendations = recommend_actions(transformed_query, k=3, threshold=0.25)

        response = ChatResponse(
            answer=answer,
            sources=sources,
            provider=provider,
            model=model,
            latency_ms=latency_ms,
            generated_at=self._now(),
            recommendations=recommendations,
            conversation_id=conversation_id,
            needs_internet=needs_internet,
        )

        await self._save_assistant_response(
            conversation_id=conversation_id,
            tenant_id=request.tenant_id,
            answer=answer
        )
        
        await self.session.commit()
        
        if request.conversation_id:
            await self.publisher.publish(
                f"conversation:{request.conversation_id}",
                {
                    "type": "chat.complete",
                    "conversation_id": request.conversation_id,
                    "tenant_id": request.tenant_id,
                    "payload": response.model_dump(),
                },
            )
        return response
    
    async def _save_assistant_response(self, conversation_id: str, tenant_id: str, answer: str):
        """Helper to save assistant response"""
        assistant_message = await self.message_service.save_message(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            rewritten_content=None,
            provider_metadata={
                "response_info": {
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        return assistant_message

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)