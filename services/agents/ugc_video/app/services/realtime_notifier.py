"""
Realtime notification service for UGC Video
Publishes events to Redis channels for frontend WebSocket subscriptions
"""
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any
from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool
from app.core.config import get_settings

_redis_pool: Optional[ConnectionPool] = None
_redis_client: Optional[Redis] = None


async def get_redis_client() -> Optional[Redis]:
    """Get or create Redis client"""
    global _redis_client, _redis_pool
    
    if _redis_client:
        return _redis_client
    
    settings = get_settings()
    redis_url = getattr(settings, 'redis_url', None) or os.getenv('REDIS_URL')
    
    if not redis_url:
        print("⚠️  Redis not configured - realtime notifications disabled")
        return None
    
    try:
        _redis_pool = ConnectionPool.from_url(redis_url, encoding="utf-8", decode_responses=True)
        _redis_client = Redis(connection_pool=_redis_pool)
        # Test connection
        await _redis_client.ping()
        print("✅ Redis connected - realtime notifications enabled")
        return _redis_client
    except Exception as e:
        print(f"⚠️  Failed to connect to Redis: {e} - realtime notifications disabled")
        return None


def get_channel_name(tenant_id: str, conversation_id: str) -> str:
    """Generate Redis channel name for tenant + conversation"""
    return f"ugc:tenant:{tenant_id}:conversation:{conversation_id}:events"


async def publish_event(
    tenant_id: str,
    conversation_id: str,
    event_type: str,
    data: Dict[str, Any],
    status: Optional[str] = None
) -> bool:
    """
    Publish event to Redis channel
    
    Args:
        tenant_id: Tenant ID
        conversation_id: Conversation ID
        event_type: Event type (JOB_STARTED, JOB_PROGRESS, JOB_COMPLETED, JOB_ERROR)
        data: Event data payload
        status: Optional status (pending, processing, completed, failed)
    
    Returns:
        True if published, False otherwise
    """
    redis = await get_redis_client()
    if not redis:
        return False
    
    channel = get_channel_name(tenant_id, conversation_id)
    
    payload = {
        "type": event_type,
        "conversation_id": conversation_id,
        "tenant_id": tenant_id,
        "status": status or "processing",
        "data": data,
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        await redis.publish(channel, json.dumps(payload))
        return True
    except Exception as e:
        print(f"⚠️  Failed to publish event to Redis: {e}")
        return False


# Convenience functions for common events
async def notify_job_started(
    tenant_id: str,
    conversation_id: str,
    job_type: str,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """Notify that a job has started"""
    return await publish_event(
        tenant_id,
        conversation_id,
        "JOB_STARTED",
        {
            "job_type": job_type,
            "metadata": metadata or {}
        },
        status="pending"
    )


async def notify_job_progress(
    tenant_id: str,
    conversation_id: str,
    job_type: str,
    progress: Dict[str, Any],
    message: Optional[str] = None
) -> bool:
    """Notify job progress update"""
    return await publish_event(
        tenant_id,
        conversation_id,
        "JOB_PROGRESS",
        {
            "job_type": job_type,
            "progress": progress,
            "message": message
        },
        status="processing"
    )


async def notify_job_completed(
    tenant_id: str,
    conversation_id: str,
    job_type: str,
    result: Dict[str, Any]
) -> bool:
    """Notify that a job has completed"""
    return await publish_event(
        tenant_id,
        conversation_id,
        "JOB_COMPLETED",
        {
            "job_type": job_type,
            "result": result
        },
        status="completed"
    )


async def notify_job_error(
    tenant_id: str,
    conversation_id: str,
    job_type: str,
    error: str,
    error_details: Optional[Dict[str, Any]] = None
) -> bool:
    """Notify that a job has failed"""
    return await publish_event(
        tenant_id,
        conversation_id,
        "JOB_ERROR",
        {
            "job_type": job_type,
            "error": error,
            "error_details": error_details or {}
        },
        status="failed"
    )
