from fastapi import APIRouter, Form
from typing import Optional
from langsmith import Client
from app.core.config import settings

router = APIRouter()

@router.post("/feedback")
async def submit_feedback(
    session_id: str = Form(...),
    image_url: str = Form(...),
    score: int = Form(...),  # 1 for Like, -1 for Dislike
    run_id: Optional[str] = Form(None)
):
    """Logs user feedback to LangSmith."""
    try:
        client = Client()
        
        kwargs = {
            "key": "user_score",
            "score": score,
            "comment": f"Feedback for image: {image_url}",
        }
        if run_id:
            kwargs["run_id"] = run_id
        else:
            kwargs["project_name"] = settings.LANGCHAIN_PROJECT
            
        client.create_feedback(**kwargs)
        return {"status": "success", "message": "Feedback recorded"}
    except Exception as e:
        print(f"Feedback Error: {e}")
        return {"status": "error", "message": str(e)}
