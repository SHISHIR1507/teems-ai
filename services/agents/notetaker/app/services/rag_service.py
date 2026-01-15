import numpy as np
from typing import List, Dict
from app.services.chunker import chunk_text_for_rag
from app.services.embeddings import embedder
from app.services.llm import llm
from app.models.call import CallChunk

class RAGService:
    def __init__(self):
        pass
    
    async def process_meeting_for_rag(self, call_data: Dict, db):
        """Chunk meeting and create embeddings"""
        
        if not call_data.get("transcript"):
            return 0
        
        # Chunk transcript
        chunks = chunk_text_for_rag(call_data["transcript"]) 
        
        if not chunks:
            return 0
        
        # Get embeddings 
        embeddings = await embedder.embed(chunks)
        
        # Save to database
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_record = CallChunk(
                call_id=call_data["id"],
                chunk_index=idx,
                content_type="transcript",
                content=chunk,
                embedding=embedding
            )
            db.add(chunk_record)
        
        db.commit()
        return len(chunks)
    
    async def search_relevant_chunks(self, query: str, call_id: str, db, top_k: int = 5) -> List[str]:
        """Find relevant chunks using vector similarity"""

        # Get query embedding (same as before)
        query_embedding = await embedder.embed_one(query)
        
        # NEW: Database does vector search - NO Python loop!
        chunks = db.query(CallChunk).filter(
            CallChunk.call_id == call_id
        ).order_by(
            CallChunk.embedding.cosine_distance(query_embedding)
        ).limit(top_k).all()
        
        if not chunks:
            return []
        
        # Return just the content (already sorted by database!)
        return [chunk.content for chunk in chunks]
    
    async def generate_answer(self, query: str, context_chunks: List[str], meeting_title: str) -> str:
        
        # Build context 
        context = "\n\n---\n\n".join([
            f"[Context {i+1}]\n{chunk}"
            for i, chunk in enumerate(context_chunks[:3])  # Limit to 3 chunks
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
        
        return answer
    
    @staticmethod
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity"""
        a_np = np.array(a)
        b_np = np.array(b)
        
        norm_a = np.linalg.norm(a_np)
        norm_b = np.linalg.norm(b_np)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return np.dot(a_np, b_np) / (norm_a * norm_b)

rag_service = RAGService()
