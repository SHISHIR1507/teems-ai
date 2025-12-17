from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from ..models.conversation import Message

class MessageService:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def save_message(self, **kwargs) -> Message:
        """Save a message to database"""
        
        
        message = Message(**kwargs)
        self.session.add(message)
        return message  # Always return Message object!
    
    async def get_recent_messages(
        self, 
        tenant_id: str, 
        conversation_id: str, 
        limit: int = 3
    ) -> list[Message]:
        """Get recent messages for a conversation"""
        
        # Skip if conversation_id is invalid
        if not conversation_id or conversation_id == "string":
            print(f" Skipping history - invalid conversation_id: {conversation_id}")
            return []
        
        stmt = (
            select(Message)
            .where(
                Message.tenant_id == tenant_id,
                Message.conversation_id == conversation_id
            )
            .order_by(desc(Message.created_at))
            .limit(limit * 2)
        )
        
        result = await self.session.execute(stmt)
        messages = result.scalars().all()
        
        return list(reversed(messages))