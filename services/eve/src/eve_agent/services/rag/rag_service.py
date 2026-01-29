"""
RAG (Retrieval Augmented Generation) service for question answering.
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import uuid

from .vector_store import vector_store
from .embedding import get_embedding_provider
from ...core.config import get_settings
from openai import AsyncOpenAI

settings = get_settings()


class RAGService:
    """Service for RAG-based question answering."""
    
    def __init__(self):
        self.embedding_provider = get_embedding_provider(settings)
        self.llm_client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url
        )
    
    async def query(
        self,
        db: Session,
        question: str,
        tenant_id: str,
        top_k: int = None,
        document_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Answer a question using RAG.
        
        Args:
            db: Database session
            question: User's question
            tenant_id: Tenant ID for filtering
            top_k: Number of chunks to retrieve (default from settings)
            document_id: Optional document ID to search within
        
        Returns:
            Dictionary with answer, sources, and metadata
        """
        if top_k is None:
            top_k = settings.rag_top_k
        
        print(f"💬 RAG Query: '{question}'")
        print(f"   Tenant: {tenant_id}, Top-K: {top_k}")
        
        # Step 1: Search for similar chunks
        similar_chunks = await vector_store.search_similar(
            db=db,
            query=question,
            tenant_id=tenant_id,
            top_k=top_k,
            document_id=document_id
        )
        
        if not similar_chunks:
            return {
                "answer": "I couldn't find any relevant information to answer your question.",
                "sources": [],
                "metadata": {
                    "chunks_found": 0,
                    "question": question
                }
            }
        
        # Step 2: Build context from retrieved chunks
        context_parts = []
        for idx, chunk in enumerate(similar_chunks, 1):
            context_parts.append(
                f"[Source {idx}] (Similarity: {chunk['similarity']:.2f})\n{chunk['content']}"
            )
        
        context = "\n\n".join(context_parts)
        
        # Step 3: Build prompt for LLM
        system_prompt = """You are a helpful AI assistant. Answer questions based on the provided context from documents.

Guidelines:
- Use ONLY the information from the provided context
- If the context doesn't contain enough information, say so
- Be concise but comprehensive
- Cite sources when relevant (e.g., "According to Source 1...")
- If asked about something not in the context, politely state that you don't have that information"""

        user_prompt = f"""Context from documents:

{context}

Question: {question}

Answer:"""

        # Step 4: Get answer from LLM
        print(f"🤖 Sending to LLM ({settings.llm_model})...")
        
        try:
            response = await self.llm_client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens
            )
            
            answer = response.choices[0].message.content
            
            print(f"✅ Generated answer ({len(answer)} chars)")
            
            # Step 5: Format response
            return {
                "answer": answer,
                "sources": [
                    {
                        "chunk_id": str(chunk["chunk_id"]),
                        "document_id": str(chunk["document_id"]),
                        "chunk_index": chunk["chunk_index"],
                        "content": chunk["content"][:200] + "..." if len(chunk["content"]) > 200 else chunk["content"],
                        "similarity": chunk["similarity"]
                    }
                    for chunk in similar_chunks
                ],
                "metadata": {
                    "chunks_found": len(similar_chunks),
                    "question": question,
                    "model": settings.llm_model,
                    "top_k": top_k
                }
            }
            
        except Exception as e:
            print(f"❌ LLM error: {e}")
            return {
                "answer": f"Error generating answer: {str(e)}",
                "sources": [
                    {
                        "chunk_id": str(chunk["chunk_id"]),
                        "document_id": str(chunk["document_id"]),
                        "chunk_index": chunk["chunk_index"],
                        "content": chunk["content"][:200] + "..." if len(chunk["content"]) > 200 else chunk["content"],
                        "similarity": chunk["similarity"]
                    }
                    for chunk in similar_chunks
                ],
                "metadata": {
                    "chunks_found": len(similar_chunks),
                    "question": question,
                    "error": str(e)
                }
            }


# Global RAG service instance
rag_service = RAGService()
