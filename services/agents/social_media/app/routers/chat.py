"""
Chat router - AI chat interface powered by CrewAI
"""

from fastapi import APIRouter, HTTPException
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.crew_service import get_crew_service

router = APIRouter()


@router.post("/v1/chat", response_model=ChatResponse, tags=["chat"])
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Chat with AI assistant powered by CrewAI to post to multiple platforms.
    
    Uses CrewAI framework with clean AIML API integration.
    The agent has tools for multi-platform posting.
    
    The agent can:
    - Post videos to TikTok (working)
    - Post to Facebook (coming soon)
    - Get your post history
    
    Send natural language messages like:
    - "Post this video https://... to TikTok with caption 'Hello'"
    - "What platforms do you support?"
    - "Show me my posts"
    """
    try:
        crew = get_crew_service()
        result = crew.process_message(request.user_id, request.message)
        
        return ChatResponse(
            message=result,
            action_taken="crew_ai_processed"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
