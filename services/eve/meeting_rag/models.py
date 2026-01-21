from sqlalchemy import Column, String, Text, JSON, DateTime, ForeignKey, Integer, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import uuid
from datetime import datetime
from pgvector.sqlalchemy import Vector


Base = declarative_base()

class Call(Base):
    __tablename__ = "calls"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id = Column(String)    
    title = Column(String)
    meeting_link = Column(Text)
    start_time = Column(DateTime)
    transcript = Column(Text)  # [{"speaker": "John", "text": "Hello"}]
    summary = Column(Text)
    action_items = Column(JSON)  # ["Task 1", "Task 2"]
    created_at = Column(DateTime, default=datetime.utcnow)

class CallChunk(Base):
    __tablename__ = "call_chunks"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    call_id = Column(String, ForeignKey("calls.id"))
    chunk_index = Column(Integer)
    content_type = Column(String)  # 'transcript', 'summary', 'action_items'
    content = Column(Text)
    embedding = Column(Vector(1536))  # PgVector type
    created_at = Column(DateTime, default=datetime.utcnow)