"""
Conversation summarization service
Generates concise summaries of conversations to pass context to specialized agents
"""
from typing import List, Dict
from loguru import logger
import httpx
from ..core.config import get_settings

settings = get_settings()

# Cache for summaries (session_id + agent_id -> summary)
_summary_cache: Dict[str, str] = {}


def _get_cache_key(session_id: str, agent_id: str) -> str:
    """Generate cache key for summary"""
    return f"{session_id}:{agent_id}"


async def summarize_conversation(
    recent_messages: List[Dict],
    agent_name: str
) -> str:
    """
    Generate a concise summary of conversation for passing to an agent.
    
    Args:
        recent_messages: List of message dicts with 'role' and 'content' keys
        agent_name: Name of the agent this summary will be passed to
    
    Returns:
        Formatted summary string: "Context from Eve: [summary]"
    """
    if not recent_messages:
        logger.info("No messages to summarize")
        return ""
    
    # Format messages for LLM
    formatted_messages = []
    for msg in recent_messages:
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        if role == 'user':
            formatted_messages.append(f"User: {content}")
        elif role == 'assistant':
            formatted_messages.append(f"Eve: {content}")
    
    conversation_text = "\n".join(formatted_messages)
    
    # Create prompt for summarization
    prompt = f"""Summarize this conversation in 2-3 sentences, focusing on what the user wants to accomplish. 
This context will be passed to {agent_name} to continue the conversation seamlessly.

Conversation:
{conversation_text}

Summary:"""
    
    try:
        # Call AIML API for summarization
        aiml_url = f"{settings.aiml_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.aiml_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "openai/gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that creates concise conversation summaries."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 150,
            "temperature": 0.3
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(aiml_url, headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            summary = result["choices"][0]["message"]["content"].strip()
        
        # Limit to 200 characters
        if len(summary) > 200:
            summary = summary[:197] + "..."
        
        # Format with prefix
        formatted_summary = f"Context from Eve: {summary}"
        
        logger.info(f"Generated conversation summary for {agent_name}: {summary[:50]}...")
        return formatted_summary
        
    except Exception as e:
        logger.warning(f"Failed to generate conversation summary: {e}")
        return ""


def get_cached_summary(session_id: str, agent_id: str) -> str:
    """Get cached summary if available"""
    cache_key = _get_cache_key(session_id, agent_id)
    return _summary_cache.get(cache_key, "")


def cache_summary(session_id: str, agent_id: str, summary: str):
    """Cache a summary"""
    cache_key = _get_cache_key(session_id, agent_id)
    _summary_cache[cache_key] = summary
    # Limit cache size (keep last 100 entries)
    if len(_summary_cache) > 100:
        # Remove oldest entries (simple FIFO)
        keys_to_remove = list(_summary_cache.keys())[:len(_summary_cache) - 100]
        for key in keys_to_remove:
            del _summary_cache[key]
