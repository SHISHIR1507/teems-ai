"""
Realtime notification service for Eve Agent
Publishes events to Redis channels for frontend WebSocket subscriptions
"""
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any
from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool
from loguru import logger
from ..core.config import get_settings

_redis_pool: Optional[ConnectionPool] = None
_redis_client: Optional[Redis] = None


async def get_redis_client() -> Optional[Redis]:
    """Get or create Redis client"""
    global _redis_client, _redis_pool
    
    if _redis_client:
        return _redis_client
    
    settings = get_settings()
    redis_url = settings.redis_url or os.getenv('REDIS_URL')
    
    if not redis_url:
        logger.warning("Redis not configured - realtime notifications disabled")
        return None
    
    try:
        _redis_pool = ConnectionPool.from_url(redis_url, encoding="utf-8", decode_responses=True)
        _redis_client = Redis(connection_pool=_redis_pool)
        # Test connection
        await _redis_client.ping()
        logger.info("✅ Redis connected - realtime notifications enabled")
        return _redis_client
    except Exception as e:
        logger.warning(f"⚠️  Failed to connect to Redis: {e} - realtime notifications disabled")
        return None


def get_channel_name(tenant_id: str, session_id: str) -> str:
    """Generate Redis channel name for tenant + session"""
    return f"eve:tenant:{tenant_id}:session:{session_id}:events"


async def publish_event(
    tenant_id: str,
    session_id: str,
    event_type: str,
    data: Dict[str, Any],
    status: Optional[str] = None
) -> bool:
    """
    Publish event to Redis channel
    
    Args:
        tenant_id: Tenant ID
        session_id: Session ID
        event_type: Event type (CHAT_STARTED, CHAT_PROGRESS, CHAT_COMPLETED, CHAT_ERROR, DOCUMENT_PROCESSING, etc.)
        data: Event data payload
        status: Optional status (pending, processing, completed, failed)
    
    Returns:
        True if published, False otherwise
    """
    redis = await get_redis_client()
    if not redis:
        return False
    
    channel = get_channel_name(tenant_id, session_id)
    
    payload = {
        "type": event_type,
        "session_id": session_id,
        "tenant_id": tenant_id,
        "status": status or "processing",
        "data": data,
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        await redis.publish(channel, json.dumps(payload))
        return True
    except Exception as e:
        logger.warning(f"⚠️  Failed to publish event to Redis: {e}")
        return False


# Convenience functions for common events
async def notify_chat_started(
    tenant_id: str,
    session_id: str,
    message: str,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """Notify that a chat has started"""
    return await publish_event(
        tenant_id,
        session_id,
        "CHAT_STARTED",
        {
            "message": message,
            "metadata": metadata or {}
        },
        status="pending"
    )


async def notify_chat_progress(
    tenant_id: str,
    session_id: str,
    progress: Dict[str, Any],
    message: Optional[str] = None
) -> bool:
    """Notify chat progress update (tool calls, thinking, etc.)"""
    return await publish_event(
        tenant_id,
        session_id,
        "CHAT_PROGRESS",
        {
            "progress": progress,
            "message": message
        },
        status="processing"
    )


async def notify_chat_completed(
    tenant_id: str,
    session_id: str,
    result: Dict[str, Any]
) -> bool:
    """Notify that a chat has completed"""
    return await publish_event(
        tenant_id,
        session_id,
        "CHAT_COMPLETED",
        {
            "result": result
        },
        status="completed"
    )


async def notify_chat_error(
    tenant_id: str,
    session_id: str,
    error: str,
    error_details: Optional[Dict[str, Any]] = None
) -> bool:
    """Notify that a chat has failed"""
    return await publish_event(
        tenant_id,
        session_id,
        "CHAT_ERROR",
        {
            "error": error,
            "error_details": error_details or {}
        },
        status="failed"
    )


async def notify_document_processing(
    tenant_id: str,
    session_id: str,
    document_id: str,
    step: str,
    progress: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None
) -> bool:
    """Notify document processing progress"""
    return await publish_event(
        tenant_id,
        session_id,
        "DOCUMENT_PROCESSING",
        {
            "document_id": document_id,
            "step": step,  # upload, extract, chunk, embed, complete
            "progress": progress or {},
            "message": message
        },
        status="processing"
    )


async def notify_tool_execution(
    tenant_id: str,
    session_id: str,
    tool_name: str,
    status: str,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """Notify tool execution status"""
    return await publish_event(
        tenant_id,
        session_id,
        "TOOL_EXECUTION",
        {
            "tool_name": tool_name,
            "status": status,  # started, completed, failed
            "metadata": metadata or {}
        },
        status=status
    )
