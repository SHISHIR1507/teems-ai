"""
Realtime notification service for Social Media Agent
Publishes events to Redis channels for frontend WebSocket subscriptions
Events are consumed by the realtime workflow service and forwarded to frontend via WebSocket
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
        return None  # Graceful degradation - notifications disabled if Redis not configured
    
    try:
        _redis_pool = ConnectionPool.from_url(redis_url, encoding="utf-8", decode_responses=True)
        _redis_client = Redis(connection_pool=_redis_pool)
        # Test connection
        await _redis_client.ping()
        return _redis_client
    except Exception as e:
        print(f"⚠️  Failed to connect to Redis: {e} - realtime notifications disabled")
        return None


def get_channel_name(tenant_id: str, conversation_id: str) -> str:
    """Generate Redis channel name for tenant + conversation"""
    return f"social_media:tenant:{tenant_id}:conversation:{conversation_id}:events"


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
        event_type: Event type (VISION_ANALYSIS_STARTED, POSTING_STARTED, etc.)
        data: Event data payload
        status: Optional status (pending, processing, completed, failed)
    
    Returns:
        True if published, False otherwise (non-blocking)
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
        "timestamp": datetime.utcnow().isoformat()
    }
    
    try:
        await redis.publish(channel, json.dumps(payload))
        return True
    except Exception as e:
        # Non-blocking: log but don't raise
        print(f"⚠️  Failed to publish event to Redis: {e}")
        return False


# Convenience functions for common events

async def notify_vision_analysis_started(
    tenant_id: str,
    conversation_id: str,
    asset_id: str,
    asset_type: str
) -> bool:
    """Notify that vision analysis has started"""
    return await publish_event(
        tenant_id,
        conversation_id,
        "VISION_ANALYSIS_STARTED",
        {
            "asset_id": asset_id,
            "asset_type": asset_type,
            "message": "Analyzing content..."
        },
        status="processing"
    )


async def notify_vision_analysis_completed(
    tenant_id: str,
    conversation_id: str,
    asset_id: str,
    asset_type: str,
    success: bool = True,
    error: Optional[str] = None
) -> bool:
    """Notify that vision analysis has completed"""
    return await publish_event(
        tenant_id,
        conversation_id,
        "VISION_ANALYSIS_COMPLETED",
        {
            "asset_id": asset_id,
            "asset_type": asset_type,
            "success": success,
            "error": error
        },
        status="completed" if success else "failed"
    )


async def notify_posting_started(
    tenant_id: str,
    conversation_id: str,
    platform: str,
    video_url: str
) -> bool:
    """Notify that posting has started"""
    return await publish_event(
        tenant_id,
        conversation_id,
        "POSTING_STARTED",
        {
            "platform": platform,
            "video_url": video_url,
            "message": f"Posting to {platform.capitalize()}..."
        },
        status="pending"
    )


async def notify_posting_progress(
    tenant_id: str,
    conversation_id: str,
    platform: str,
    step: str,
    message: Optional[str] = None
) -> bool:
    """Notify posting progress update"""
    return await publish_event(
        tenant_id,
        conversation_id,
        "POSTING_PROGRESS",
        {
            "platform": platform,
            "step": step,  # "uploading", "processing", "publishing"
            "message": message or f"Processing {step}..."
        },
        status="processing"
    )


async def notify_posting_completed(
    tenant_id: str,
    conversation_id: str,
    platform: str,
    post_id: str,
    publish_id: Optional[str] = None
) -> bool:
    """Notify that posting has completed successfully"""
    return await publish_event(
        tenant_id,
        conversation_id,
        "POSTING_COMPLETED",
        {
            "platform": platform,
            "post_id": post_id,
            "publish_id": publish_id,
            "message": f"Successfully posted to {platform.capitalize()}!"
        },
        status="completed"
    )


async def notify_posting_error(
    tenant_id: str,
    conversation_id: str,
    platform: str,
    error: str,
    error_details: Optional[Dict[str, Any]] = None
) -> bool:
    """Notify that posting has failed"""
    return await publish_event(
        tenant_id,
        conversation_id,
        "POSTING_ERROR",
        {
            "platform": platform,
            "error": error,
            "error_details": error_details or {},
            "message": f"Failed to post to {platform.capitalize()}"
        },
        status="failed"
    )


async def notify_agent_processing(
    tenant_id: str,
    conversation_id: str,
    stage: str,
    message: Optional[str] = None
) -> bool:
    """Notify that agent is processing (optional, can be noisy)"""
    return await publish_event(
        tenant_id,
        conversation_id,
        "AGENT_PROCESSING",
        {
            "stage": stage,  # "collect_content", "prepare_and_confirm", etc.
            "message": message or f"Processing: {stage}"
        },
        status="processing"
    )
