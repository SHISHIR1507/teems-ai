from typing import List

def chunk_text_for_rag(text: str, max_chunk_size: int = 500) -> List[str]:
    """Simple text chunking for RAG"""
    if not text:
        return []
    
    words = text.split()
    chunks = []
    current_chunk = []
    current_length = 0
    
    for word in words:
        word_length = len(word) + 1  # +1 for space
        
        if current_length + word_length > max_chunk_size and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = []
            current_length = 0
        
        current_chunk.append(word)
        current_length += word_length
    
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    return chunks