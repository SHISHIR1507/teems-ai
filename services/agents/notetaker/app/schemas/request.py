from pydantic import BaseModel
from typing import Optional

class ScheduleRequest(BaseModel):
    meeting_link: str
    start_time: str  # ISO format: "2024-01-15T14:30:00Z"
    title: Optional[str] = "Teems.ai"  # Default to "Teems.ai"

class ChatRequest(BaseModel):
    query: str
