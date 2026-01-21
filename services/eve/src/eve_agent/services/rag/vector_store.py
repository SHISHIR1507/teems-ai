"""
Vector store operations for pgvector - storing and searching embeddings.
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
import uuid

from .embedding import get_embedding_provider
from ...config import get_settings
from ...models.document import DocumentChunk

settings = get_settings()


class VectorStore:
    """Service for vector storage and similarity search using pgvector."""
    
    def __init__(self):
        self.embedding_provider = get_embedding_provider(settings)
    
    async def store_chunks(
        self,
        db: Session,
        document_id: uuid.UUID,
        chunks: List[str],
        tenant_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[uuid.UUID]:
        """
        Store text chunks with their embeddings in the database.
        
        Args:
            db: Database session
            document_id: ID of the parent document
            chunks: List of text chunks
            tenant_id: Tenant ID for multi-tenancy
            metadata: Optional metadata for chunks
        
        Returns:
            List of chunk IDs
        """
        print(f"📦 Generating embeddings for {len(chunks)} chunks...")
        
        # Generate embeddings for all chunks
        embeddings = await self.embedding_provider.embed(chunks)
        
        print(f"✅ Generated {len(embeddings)} embeddings")
        
        # Store chunks with embeddings
        chunk_ids = []
        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            chunk = DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                tenant_id=tenant_id,
                chunk_index=idx,
                content=chunk_text,
                embedding=embedding,
                chunk_metadata=metadata or {} if metadata else None
            )
            db.add(chunk)
            chunk_ids.append(chunk.id)
        
        db.commit()
        print(f"✅ Stored {len(chunk_ids)} chunks in database")
        
        return chunk_ids
    
    async def search_similar(
        self,
        db: Session,
        query: str,
        tenant_id: str,
        top_k: int = 5,
        document_id: Optional[uuid.UUID] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar chunks using vector similarity.
        
        Args:
            db: Database session
            query: Query text
            tenant_id: Tenant ID for filtering
            top_k: Number of results to return
            document_id: Optional document ID to filter by
        
        Returns:
            List of similar chunks with metadata and similarity scores
        """
        print(f"🔍 Searching for similar chunks to: '{query[:50]}...'")
        
        # Generate embedding for query
        query_embedding = await self.embedding_provider.embed_one(query)
        
        # Build SQL query for vector similarity search
        # Using cosine distance: 1 - (embedding <=> query_embedding)
        sql_query = text("""
            SELECT 
                id,
                document_id,
                chunk_index,
                content,
                metadata,
                1 - (embedding <=> :query_embedding) as similarity
            FROM document_chunks
            WHERE tenant_id = :tenant_id
            """ + ("AND document_id = :document_id" if document_id else "") + """
            ORDER BY embedding <=> :query_embedding
            LIMIT :top_k
        """)
        
        params = {
            "query_embedding": str(query_embedding),
            "tenant_id": tenant_id,
            "top_k": top_k
        }
        
        if document_id:
            params["document_id"] = str(document_id)
        
        # Execute search
        result = db.execute(sql_query, params)
        rows = result.fetchall()
        
        # Format results
        results = []
        for row in rows:
            results.append({
                "chunk_id": row[0],
                "document_id": row[1],
                "chunk_index": row[2],
                "content": row[3],
                "metadata": row[4],
                "similarity": float(row[5])
            })
        
        print(f"✅ Found {len(results)} similar chunks")
        
        return results
    
    def delete_chunks(self, db: Session, document_id: uuid.UUID) -> int:
        """
        Delete all chunks for a document.
        
        Args:
            db: Database session
            document_id: Document ID
        
        Returns:
            Number of chunks deleted
        """
        count = db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id
        ).delete()
        
        db.commit()
        print(f"🗑️ Deleted {count} chunks for document {document_id}")
        
        return count


# Global vector store instance
vector_store = VectorStore()
