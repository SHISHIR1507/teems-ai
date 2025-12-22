import json

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import AuthenticatedUser, require_tenant
from ..config import Settings
from ..database.session import get_session
from ..dependencies import (
    get_embedding_dep,
    get_llm_factory_dep,
    get_publisher_dep,
    get_settings_dep,

    get_message_service_dep,  
    get_query_rewriter_dep,   
)
from ..services.message_service import MessageService  
from ..services.query_rewriter import QueryRewriterService  

from ..schemas.rag import ChatRequest, ChatResponse, DocumentIngestRequest, DocumentIngestResponse
from ..services.chunker import extract_text_from_upload
from ..services.embedding import EmbeddingProvider
from ..services.llm import LLMFactory
from ..services.rag import RAGService
from ..events import EventPublisher

router = APIRouter()


def get_rag_service(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    embedder: EmbeddingProvider = Depends(get_embedding_dep),
    llm_factory: LLMFactory = Depends(get_llm_factory_dep),
    publisher: EventPublisher = Depends(get_publisher_dep),

    message_service: MessageService = Depends(get_message_service_dep),
    query_rewriter: QueryRewriterService = Depends(get_query_rewriter_dep),
) -> RAGService:
    return RAGService(session, settings, embedder, llm_factory, publisher, message_service, query_rewriter)


@router.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/v1/rag/ingest/text", response_model=DocumentIngestResponse, tags=["ingest"])
async def ingest_text(
    payload: DocumentIngestRequest,
    user: AuthenticatedUser = Depends(require_tenant()),
    rag_service: RAGService = Depends(get_rag_service),
) -> DocumentIngestResponse:
    # Enforce tenant_id from the authenticated user, not from the client
    payload.tenant_id = user.tenant_id  # type: ignore[assignment]
    return await rag_service.ingest_text(payload)


@router.post("/v1/rag/ingest/file", response_model=DocumentIngestResponse, tags=["ingest"])
async def ingest_file(
    title: str | None = Form(default=None),
    metadata: str | None = Form(default=None, description="JSON metadata"),
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(require_tenant()),
    rag_service: RAGService = Depends(get_rag_service),
) -> DocumentIngestResponse:
    raw_text = await extract_text_from_upload(file)
    metadata_dict = {}
    if metadata and metadata.strip():  
        try:
            metadata_dict = json.loads(metadata)
        except json.JSONDecodeError:
            # Log and use empty dict instead of crashing
            print(f"WARNING: Invalid JSON metadata: {metadata[:50]}")
            metadata_dict = {}    
    payload = DocumentIngestRequest(
        tenant_id=user.tenant_id or "",  # validated by require_tenant
        title=title or file.filename,
        text=raw_text,
        metadata=metadata_dict,
    )
    return await rag_service.ingest_text(payload)


@router.post("/v1/rag/chat", response_model=ChatResponse, tags=["chat"])
async def chat(
    payload: ChatRequest,
    user: AuthenticatedUser = Depends(require_tenant()),
    rag_service: RAGService = Depends(get_rag_service),
):
    # Enforce tenant_id from the authenticated user
    payload.tenant_id = user.tenant_id or ""  # type: ignore[assignment]
    return await rag_service.chat(payload)

