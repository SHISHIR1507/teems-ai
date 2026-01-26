"""
Feedback router - User feedback collection
"""
from fastapi import APIRouter, HTTPException, Depends
from app.core.auth import AuthenticatedUser, require_tenant
from app.models.schemas import FeedbackRequest, FeedbackResponse
from langsmith import Client
from app.core.config import get_settings
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger("routes.feedback")


@router.post("/v1/feedback", response_model=FeedbackResponse, tags=["feedback"])
async def submit_feedback(
    request: FeedbackRequest,
    user: AuthenticatedUser = Depends(require_tenant())
) -> FeedbackResponse:
    """
    Submit user feedback (likes/dislikes) for generated images to LangSmith.
    
    This helps improve the AI model through reinforcement learning.
    """
    try:
        settings = get_settings()
        client = Client(api_key=settings.langchain_api_key if settings.langchain_api_key else None)
        
        kwargs = {
            "key": "user_score",
            "score": request.score,
            "comment": f"Feedback for image: {request.image_url}",
        }
        if request.run_id:
            kwargs["run_id"] = request.run_id
        else:
            kwargs["project_name"] = settings.langchain_project
            
        client.create_feedback(**kwargs)
        logger.info(f"Feedback recorded: score={request.score}, image={request.image_url}")
        return FeedbackResponse(
            status="success",
            message="Feedback recorded"
        )
    except Exception as e:
        logger.error(f"Feedback Error: {str(e)}")
        return FeedbackResponse(
            status="error",
            message=str(e)
        )
