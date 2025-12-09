from datetime import datetime
from typing import Optional
import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID

from ..database.base import Base


class Agent(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    title = Column(String(100), nullable=False)  # e.g., "Creative Designer", "UGC Creator"
    description = Column(Text, nullable=True)  # Full bio for detail page
    short_description = Column(String(200), nullable=True)  # For card view
    
    # Basic info
    category = Column(String(50), nullable=True)  # "Marketing", "Design", "Software"
    price = Column(String(50), nullable=True)  # "$5000", "Contact for quote"
    
    # Skills and tools (store as JSON arrays)
    skills = Column(JSON, nullable=True, default=list)  # ["Visual Design", "Branding"]
    tools_stack = Column(JSON, nullable=True, default=list)  # ["Figma", "Photoshop"]
    
    # Media URLs (will be added when S3 is ready)
    # profile_image_url = Column(String(500), nullable=True)
    # hero_image_url = Column(String(500), nullable=True)
    # intro_video_url = Column(String(500), nullable=True)
    # sample_work_urls = Column(JSON, nullable=True, default=list)  # List of URLs
    
    # Versioning
    version = Column(Integer, default=1, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Agent(name={self.name}, title={self.title})>"