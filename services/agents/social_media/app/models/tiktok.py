"""
SQLAlchemy models for TikTok posting service
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class UserToken(Base):
    """Store TikTok access tokens for users"""
    __tablename__ = "user_tokens"

    user_id = Column(Integer, primary_key=True)
    platform = Column(String(50), primary_key=True, default="tiktok")
    access_token = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Post(Base):
    """Track posted TikTok content"""
    __tablename__ = "posts"

    post_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    platform = Column(String(50), default="tiktok", nullable=False)
    video_url = Column(Text, nullable=False)
    caption = Column(Text, nullable=True)
    hashtags = Column(Text, nullable=True)
    status = Column(String(20), default="posted", nullable=False)
    publish_id = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)
