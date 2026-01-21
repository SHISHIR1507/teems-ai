"""
SQLAlchemy models for documents and document_chunks tables.
"""
from sqlalchemy import Column, String, Integer, BigInteger, Text, ForeignKey, JSON, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from datetime import datetime
import uuid

from ..database.base import Base


class Document(Base):
    """Document model - maps to existing 'documents' table."""
    
    __tablename__ = "documents"
    
    # Existing columns
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(128), nullable=False, index=True)
    title = Column(String(255), nullable=True)
    doc_metadata = Column("metadata", JSON, nullable=True)  # Renamed to avoid SQLAlchemy conflict
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    
    # New columns for RAG system (will be added via migration)
    filename = Column(String(255), nullable=True)
    s3_url = Column(Text, nullable=True)
    s3_key = Column(Text, nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    total_chunks = Column(Integer, nullable=True)
    status = Column(String(50), nullable=True, default="uploaded")
    
    # Relationship
    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<Document(id={self.id}, title={self.title}, chunks={self.total_chunks})>"


class DocumentChunk(Base):
    """DocumentChunk model - maps to existing 'document_chunks' table."""
    
    __tablename__ = "document_chunks"
    
    # Existing columns
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(128), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    chunk_metadata = Column("metadata", JSON, nullable=True)  # Renamed to avoid SQLAlchemy conflict
    embedding = Column(Vector(1536), nullable=True)  # Default to 1536 dims, adjust if needed
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    document = relationship("Document", back_populates="chunks")
    
    def __repr__(self):
        return f"<DocumentChunk(id={self.id}, document_id={self.document_id}, index={self.chunk_index})>"
