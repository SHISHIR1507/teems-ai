import json

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..database.session import get_session
from ..dependencies import get_embedding_dep, get_llm_factory_dep, get_settings_dep
from ..schemas.rag import ChatRequest, DocumentIngestRequest, DocumentIngestResponse
from ..services.chunker import extract_text_from_upload
from ..services.embedding import EmbeddingProvider
from ..services.llm import LLMFactory
from ..services.rag import RAGService

router = APIRouter()


def get_rag_service(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    embedder: EmbeddingProvider = Depends(get_embedding_dep),
    llm_factory: LLMFactory = Depends(get_llm_factory_dep),
) -> RAGService:
    return RAGService(session, settings, embedder, llm_factory)


@router.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/v1/rag/ingest/text", response_model=DocumentIngestResponse, tags=["ingest"])
async def ingest_text(
    payload: DocumentIngestRequest,
    rag_service: RAGService = Depends(get_rag_service),
) -> DocumentIngestResponse:
    return await rag_service.ingest_text(payload)


@router.post("/v1/rag/ingest/file", response_model=DocumentIngestResponse, tags=["ingest"])
async def ingest_file(
    tenant_id: str = Form(...),
    title: str | None = Form(default=None),
    metadata: str | None = Form(default=None, description="JSON metadata"),
    file: UploadFile = File(...),
    rag_service: RAGService = Depends(get_rag_service),
) -> DocumentIngestResponse:
    raw_text = await extract_text_from_upload(file)
    metadata_dict = json.loads(metadata) if metadata else {}
    payload = DocumentIngestRequest(
        tenant_id=tenant_id,
        title=title or file.filename,
        text=raw_text,
        metadata=metadata_dict,
    )
    return await rag_service.ingest_text(payload)


@router.post("/v1/rag/chat", tags=["chat"])
async def chat(
    payload: ChatRequest,
    rag_service: RAGService = Depends(get_rag_service),
):
    return await rag_service.chat(payload)

