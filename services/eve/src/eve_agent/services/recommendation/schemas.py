"""
Schemas for recommendation system
"""
from dataclasses import dataclass
from typing import Union, Optional

@dataclass
class RecommendationItem:
    """Represents a single recommended action or agent"""
    action: str
    score: float
    id: Union[str, int]  # Can be string ID or integer index
    type: str = "action"  # "action" or "agent"
    # Agent-specific fields (optional)
    agent_id: Optional[str] = None  # Eve agent ID (e.g., "ugc_creator")
    agent_manager_id: Optional[str] = None  # UUID from agent-manager
    agent_name: Optional[str] = None
    is_assigned: Optional[bool] = None
    ui_route: Optional[str] = None
    click_action: Optional[str] = None  # "navigate" or "chat_followup"
