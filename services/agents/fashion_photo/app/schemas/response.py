from pydantic import BaseModel
from typing import List, Optional

class AvatarSelectionResponse(BaseModel):
    status: str
    message: str
    stage: str

class UploadResponse(BaseModel):
    status: str
    urls: List[str]
    stage: str
    message: str

class ChatResponse(BaseModel):
    status: str
    output: str
    run_id: Optional[str] = None

class FeedbackResponse(BaseModel):
    status: str
    message: str
