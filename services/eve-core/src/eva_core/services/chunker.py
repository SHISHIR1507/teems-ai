from __future__ import annotations

import io
from typing import Iterable

from fastapi import HTTPException, UploadFile, status
from pypdf import PdfReader
from docx import Document as DocxDocument


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")

    cleaned = text.replace("\r\n", "\n")
    segments: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        segments.append(cleaned[start:end])
        if end == len(cleaned):
            break
        start = end - overlap
    return segments


async def extract_text_from_upload(file: UploadFile) -> str:
    contents = await file.read()
    filename = file.filename.lower() if file.filename else "upload"

    if filename.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(contents))
        parts = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(parts)

    if filename.endswith(".docx"):
        doc = DocxDocument(io.BytesIO(contents))
        return "\n".join(paragraph.text for paragraph in doc.paragraphs)

    if filename.endswith(".txt"):
        return contents.decode("utf-8")

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported file type. Please upload PDF, DOCX, or TXT files.",
    )

