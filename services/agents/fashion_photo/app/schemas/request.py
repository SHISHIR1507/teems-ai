from pydantic import BaseModel
from typing import Optional

class AvatarSelectionRequest(BaseModel):
    session_id: str
    avatar_url: str

class ChatRequest(BaseModel):
    session_id: str
    message: str = ""

class FeedbackRequest(BaseModel):
    session_id: str
    image_url: str
    score: int
    run_id: Optional[str] = None
