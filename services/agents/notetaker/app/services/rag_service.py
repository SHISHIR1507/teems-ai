"""
RAG (Retrieval-Augmented Generation) service for meeting queries
"""
import numpy as np
from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.services.chunker import chunk_text_for_rag
from app.services.embeddings import embedder
from app.services.llm import llm
from app.models.call import CallChunk, Call

logger = logging.getLogger(__name__)


class RAGService:
    """Service for RAG-powered meeting queries"""
    
    def __init__(self):
        pass
    
    async def process_meeting_for_rag(self, call_data: Dict, db: AsyncSession) -> int:
        """
        Chunk meeting transcript and create embeddings for RAG
        
        Args:
            call_data: Dict with 'id' and 'transcript' keys
            db: Database session
        
        Returns:
            Number of chunks created
        """
        try:
            if not call_data.get("transcript"):
                logger.warning(f"No transcript in call_data for call {call_data.get('id')}")
                return 0
            
            transcript = call_data["transcript"]
            call_id = call_data["id"]
            tenant_id = call_data.get("tenant_id")
            
            # Chunk transcript
            chunks = chunk_text_for_rag(transcript)
            
            if not chunks:
                logger.warning(f"No chunks created for call {call_id}")
                return 0
            
            logger.info(f"Created {len(chunks)} chunks for call {call_id}")
            
            # Get embeddings
            embeddings = await embedder.embed(chunks)
            
            if len(embeddings) != len(chunks):
                logger.error(f"Embedding count mismatch: {len(embeddings)} embeddings for {len(chunks)} chunks")
                return 0
            
            # Save to database
            for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_record = CallChunk(
                    call_id=call_id,
                    tenant_id=tenant_id,
                    chunk_index=idx,
                    content_type="transcript",
                    content=chunk,
                    embedding=embedding
                )
                db.add(chunk_record)
            
            await db.commit()
            logger.info(f"Successfully saved {len(chunks)} chunks with embeddings for call {call_id}")
            return len(chunks)
        
        except Exception as e:
            logger.error(f"Error processing meeting for RAG: {e}", exc_info=True)
            await db.rollback()
            return 0
    
    async def search_relevant_chunks(
        self,
        query: str,
        call_id: str,
        db: AsyncSession,
        top_k: int = 5
    ) -> List[str]:
        """
        Find relevant chunks using vector similarity search
        
        Args:
            query: User's query string
            call_id: Call ID to search within
            db: Database session
            top_k: Number of top chunks to return
        
        Returns:
            List of chunk content strings (sorted by relevance)
        """
        try:
            # Get query embedding
            query_embedding = await embedder.embed_one(query)
            
            if not query_embedding:
                logger.warning(f"Failed to generate embedding for query: {query}")
                return []
            
            # Database does vector search using cosine distance
            result = await db.execute(
                select(CallChunk)
                .filter(CallChunk.call_id == call_id)
                .order_by(CallChunk.embedding.cosine_distance(query_embedding))
                .limit(top_k)
            )
            chunks = result.scalars().all()
            
            if not chunks:
                logger.info(f"No chunks found for call {call_id}")
                return []
            
            logger.info(f"Found {len(chunks)} relevant chunks for query in call {call_id}")
            
            # Return just the content (already sorted by database!)
            return [chunk.content for chunk in chunks]
        
        except Exception as e:
            logger.error(f"Error searching relevant chunks: {e}", exc_info=True)
            return []
    
    async def search_relevant_chunks_for_user(
        self,
        query: str,
        tenant_id: str,
        user_id: str,
        db: AsyncSession,
        top_k: int = 20
    ) -> List[Dict]:
        """
        Find relevant chunks across all meetings for a given user using vector similarity search.
        
        Args:
            query: User's query string
            tenant_id: Tenant ID for multi-tenancy isolation
            user_id: Auth0 user ID (sub) to scope meetings
            db: Database session
            top_k: Number of top chunks to return
        
        Returns:
            List of dicts containing:
                - content: chunk text
                - call_id: associated call ID
                - meeting_title: associated meeting title
        """
        try:
            # Get query embedding
            query_embedding = await embedder.embed_one(query)
            
            if not query_embedding:
                logger.warning(f"Failed to generate embedding for query: {query}")
                return []
            
            # Vector search across all completed calls for this user and tenant
            stmt = (
                select(CallChunk, Call)
                .join(Call, CallChunk.call_id == Call.id)
                .filter(
                    Call.tenant_id == tenant_id,
                    Call.user_id == user_id,
                    Call.status == "completed",
                )
                .order_by(CallChunk.embedding.cosine_distance(query_embedding))
                .limit(top_k)
            )
            
            result = await db.execute(stmt)
            rows = result.all()
            
            if not rows:
                logger.info(
                    "No chunks found for tenant %s user %s", tenant_id, user_id
                )
                return []
            
            logger.info(
                "Found %d relevant chunks for query for tenant %s user %s",
                len(rows),
                tenant_id,
                user_id,
            )
            
            # Each row is (CallChunk, Call)
            chunks_with_meta: List[Dict] = []
            for chunk, call in rows:
                chunks_with_meta.append(
                    {
                        "content": chunk.content,
                        "call_id": call.id,
                        "meeting_title": call.title,
                    }
                )
            
            return chunks_with_meta
        
        except Exception as e:
            logger.error(
                "Error searching relevant chunks for user %s in tenant %s: %s",
                user_id,
                tenant_id,
                e,
                exc_info=True,
            )
            return []
    
    async def generate_answer(
        self,
        query: str,
        context_chunks: List[str],
        meeting_title: str
    ) -> str:
        """
        Generate answer using LLM with retrieved context
        
        Args:
            query: User's question
            context_chunks: Relevant context chunks
            meeting_title: Title of the meeting
        
        Returns:
            Generated answer string
        """
        try:
            # Build context (limit to top 3 chunks to avoid token limits)
            context = "\n\n---\n\n".join([
                f"[Context {i+1}]\n{chunk}"
                for i, chunk in enumerate(context_chunks[:3])
            ])
            
            prompt = f"""You are a helpful meeting assistant. Answer questions intelligently based on meeting context.

SMART RESPONSE GUIDELINES:

1. FOR ACTION ITEMS REQUESTS ("action items", "tasks", "to-do", "next steps"):
- Extract any mentioned tasks from context
- If none explicitly mentioned, infer likely action items from discussion
- Format as bullet points with responsible persons if mentioned

2. FOR TRANSCRIPT REQUESTS ("transcript", "what was said", "conversation"):
- Summarize key discussions from context
- Mention main speakers and topics
- Provide comprehensive overview

3. FOR SUMMARY REQUESTS ("summary", "overview", "main points"):
- Provide concise yet complete summary
- Highlight decisions, key topics, action items

4. FOR SPECIFIC QUESTIONS:
- Answer based on context provided
- If context doesn't have exact answer, provide related information
- Reference speakers when possible

5. GENERAL RULE:
- Be helpful, not restrictive
- Provide useful information from context
- Use natural, conversational tone

Meeting: {meeting_title}

Meeting Context:
{context}

Question: {query}

Provide a helpful answer:"""
            
            messages = [{"role": "user", "content": prompt}]
            answer = await llm.generate(messages)
            
            if not answer:
                logger.warning(f"Empty answer generated for query: {query}")
                return "I apologize, but I couldn't generate a response. Please try rephrasing your question."
            
            return answer
        
        except Exception as e:
            logger.error(f"Error generating answer: {e}", exc_info=True)
            return "I apologize, but I encountered an error while generating a response. Please try again."
    
    @staticmethod
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors
        
        Args:
            a: First vector
            b: Second vector
        
        Returns:
            Cosine similarity score (0-1)
        """
        try:
            a_np = np.array(a)
            b_np = np.array(b)
            
            norm_a = np.linalg.norm(a_np)
            norm_b = np.linalg.norm(b_np)
            
            if norm_a == 0 or norm_b == 0:
                return 0.0
            
            return np.dot(a_np, b_np) / (norm_a * norm_b)
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0


# Singleton instance
rag_service = RAGService()
