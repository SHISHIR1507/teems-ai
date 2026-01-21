"""
Schemas for recommendation system
"""
from dataclasses import dataclass
from typing import Union

@dataclass
class RecommendationItem:
    """Represents a single recommended action"""
    action: str
    score: float
    id: Union[str, int]  # Can be string ID or integer index
