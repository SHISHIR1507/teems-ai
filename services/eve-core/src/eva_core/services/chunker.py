from __future__ import annotations

import io
import os
import tempfile
from typing import Iterable, List
import json
import csv

from fastapi import HTTPException, UploadFile, status
from pypdf import PdfReader
from docx import Document as DocxDocument


import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter
from docling.document_converter import DocumentConverter
from docling_core.types.doc import TableItem, TextItem
from .ocr_service import process_uploaded_image, process_uploaded_pdf



def extract_tables_preserve_text(path: str) -> str:
    converter = DocumentConverter()
    result = converter.convert(path)
    doc = result.document

    output_parts = []

    for item_tuple in doc.iterate_items():
        try:
            item, parent = item_tuple
        except:
            item = item_tuple

        # TABLE - Preserve as HTML
        if isinstance(item, TableItem):
            try:
                html = item.export_to_html(doc=doc)
                output_parts.append(html)
            except:
                try:
                    html = doc.export_to_html()
                    output_parts.append(html)
                except:
                    output_parts.append("<TABLE_EXTRACT_FAILED/>")

        # TEXT
        elif isinstance(item, TextItem):
            if item.text and item.text.strip():
                output_parts.append(item.text)

    return "\n".join(output_parts)


def extract_txt_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def extract_json_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return json.dumps(data, indent=2, ensure_ascii=False)


def extract_csv_text(path: str) -> str:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(" | ".join(row))
    return "\n".join(rows)


def load_document_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()

    if ext in [".pdf", ".docx"]:
        return extract_tables_preserve_text(path)

    if ext == ".txt":
        return extract_txt_text(path)

    if ext == ".json":
        return extract_json_text(path)

    if ext == ".csv":
        return extract_csv_text(path)

    raise ValueError(f"Unsupported file type: {ext}")


def get_token_encoder(model_name: str = "gpt-4o-mini"):
    try:
        return tiktoken.encoding_for_model(model_name)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")


def chunk_text_token_based(
    text: str,
    chunk_tokens: int = 350,
    overlap_tokens: int = 50,
    model_name: str = "gpt-4o-mini",
) -> List[str]:
    encoding = get_token_encoder(model_name)

    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name=encoding.name,
        chunk_size=chunk_tokens,
        chunk_overlap=overlap_tokens,
        separators=[
            "\n\n",  # paragraphs
            "\n",    # headers/lists
            ". ",    # sentence boundary
            " ",     # word boundary
            ""       # fallback to characters
        ],
    )

    return splitter.split_text(text)


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    
    chunk_tokens = max(100, chunk_size // 4)  # Minimum 100 tokens
    overlap_tokens = max(20, overlap // 4)    # Minimum 20 tokens
    
    # token-based chunking
    return chunk_text_token_based(
        text=text,
        chunk_tokens=chunk_tokens,
        overlap_tokens=overlap_tokens,
        model_name="gpt-4o-mini"  # Using GPT-4 tokenizer as default
    )


async def extract_text_from_upload(file: UploadFile) -> str:
    contents = await file.read()
    filename = file.filename.lower() if file.filename else "upload"
    
    if filename.endswith(('.png', '.jpg', '.jpeg')):
        try:
            file.file = io.BytesIO(contents)
            from .ocr_service import process_uploaded_image
            from ..config import get_settings
            settings = get_settings()
            api_key = getattr(settings, 'gemini_api_key', None)
            return await process_uploaded_image(file, api_key)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Image processing failed: {str(e)}",
            )
    
    # Save to temp file for other formats
    suffix = os.path.splitext(filename)[1] or ".tmp"
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(contents)
        temp_path = tmp.name
    
    try:
        text = load_document_text(temp_path)
        cleaned = "\n".join(line.rstrip() for line in text.splitlines())
        
        if filename.endswith('.pdf') and len(cleaned.strip()) < 200:
            file.file = io.BytesIO(contents)
            from .ocr_service import process_uploaded_pdf
            from ..config import get_settings
            settings = get_settings()
            api_key = getattr(settings, 'gemini_api_key', None)
            return await process_uploaded_pdf(file, api_key)
        
        return cleaned
        
    except ValueError as e:
        # Original fallback logic
        ext = os.path.splitext(filename)[1].lower()
        
        if ext == ".pdf":
            reader = PdfReader(io.BytesIO(contents))
            parts = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(parts)
            
        elif ext == ".docx":
            doc = DocxDocument(io.BytesIO(contents))
            return "\n".join(paragraph.text for paragraph in doc.paragraphs)
            
        elif ext == ".txt":
            return contents.decode("utf-8")
            
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {ext}",
            )
    
    finally:
        try:
            os.unlink(temp_path)
        except:
            pass


def ingest_and_chunk(
    path: str,
    chunk_tokens: int = 350,
    overlap_tokens: int = 50,
    model_name: str = "gpt-4o-mini",
) -> dict:
    
    raw_text = load_document_text(path)
    
    cleaned = "\n".join(line.rstrip() for line in raw_text.splitlines())

    chunks = chunk_text_token_based(
        cleaned,
        chunk_tokens=chunk_tokens,
        overlap_tokens=overlap_tokens,
        model_name=model_name,
    )

    return {
        "path": path,
        "num_chunks": len(chunks),
        "chunks": chunks
    }