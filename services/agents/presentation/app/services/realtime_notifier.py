"""
Realtime notification service for Presentation Agent
Publishes events to Redis channels for frontend WebSocket subscriptions
Events are consumed by the realtime workflow service and forwarded to frontend via WebSocket
"""
import json
import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool
from app.core.config import get_settings

logger = logging.getLogger("presentation_agent.realtime_notifier")
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
        logger.info("✅ Redis connected - realtime notifications enabled")
        return _redis_client
    except Exception as e:
        logger.warning(f"⚠️  Failed to connect to Redis: {e} - realtime notifications disabled")
        return None


def get_channel_name(tenant_id: str, conversation_id: str) -> str:
    """Generate Redis channel name for tenant + conversation"""
    return f"presentation:tenant:{tenant_id}:conversation:{conversation_id}:events"


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
        event_type: Event type (PRESENTATION_GENERATION_STARTED, etc.)
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
        logger.debug(f"Published event {event_type} to channel {channel}")
        return True
    except Exception as e:
        # Non-blocking: log but don't raise
        logger.warning(f"⚠️  Failed to publish event to Redis: {e}")
        return False


# Convenience functions for presentation events

async def notify_presentation_generation_started(
    tenant_id: str,
    conversation_id: str,
    task_id: str,
    presentation_id: str,
    estimated_time_seconds: Optional[int] = None
) -> bool:
    """Notify that presentation generation has started"""
    return await publish_event(
        tenant_id,
        conversation_id,
        "PRESENTATION_GENERATION_STARTED",
        {
            "task_id": task_id,
            "presentation_id": presentation_id,
            "message": "Generating your presentation...",
            "estimated_time_seconds": estimated_time_seconds or 60
        },
        status="processing"
    )


async def notify_presentation_generation_completed(
    tenant_id: str,
    conversation_id: str,
    task_id: str,
    presentation_id: str,
    download_url: Optional[str] = None,
    s3_url: Optional[str] = None,
    slides_count: Optional[int] = None,
    success: bool = True,
    error: Optional[str] = None
) -> bool:
    """Notify that presentation generation has completed"""
    return await publish_event(
        tenant_id,
        conversation_id,
        "PRESENTATION_GENERATION_COMPLETED",
        {
            "task_id": task_id,
            "presentation_id": presentation_id,
            "download_url": download_url,
            "s3_url": s3_url,
            "slides_count": slides_count,
            "success": success,
            "error": error,
            "message": "Presentation generated successfully!" if success else f"Generation failed: {error}"
        },
        status="completed" if success else "failed"
    )


async def notify_presentation_edit_started(
    tenant_id: str,
    conversation_id: str,
    task_id: str,
    presentation_id: str,
    edit_type: str = "edit"
) -> bool:
    """Notify that presentation editing has started"""
    return await publish_event(
        tenant_id,
        conversation_id,
        "PRESENTATION_EDIT_STARTED",
        {
            "task_id": task_id,
            "presentation_id": presentation_id,
            "edit_type": edit_type,
            "message": "Editing your presentation..."
        },
        status="processing"
    )


async def notify_presentation_edit_completed(
    tenant_id: str,
    conversation_id: str,
    task_id: str,
    presentation_id: str,
    download_url: Optional[str] = None,
    s3_url: Optional[str] = None,
    success: bool = True,
    error: Optional[str] = None
) -> bool:
    """Notify that presentation editing has completed"""
    return await publish_event(
        tenant_id,
        conversation_id,
        "PRESENTATION_EDIT_COMPLETED",
        {
            "task_id": task_id,
            "presentation_id": presentation_id,
            "download_url": download_url,
            "s3_url": s3_url,
            "success": success,
            "error": error,
            "message": "Presentation edited successfully!" if success else f"Edit failed: {error}"
        },
        status="completed" if success else "failed"
    )


async def notify_document_upload_started(
    tenant_id: str,
    conversation_id: str,
    document_id: str,
    filename: str
) -> bool:
    """Notify that document upload has started"""
    return await publish_event(
        tenant_id,
        conversation_id,
        "DOCUMENT_UPLOAD_STARTED",
        {
            "document_id": document_id,
            "filename": filename,
            "message": f"Uploading {filename}..."
        },
        status="processing"
    )


async def notify_document_processing_started(
    tenant_id: str,
    conversation_id: str,
    document_id: str,
    slidespeak_document_id: str,
    filename: str
) -> bool:
    """Notify that document processing has started"""
    return await publish_event(
        tenant_id,
        conversation_id,
        "DOCUMENT_PROCESSING_STARTED",
        {
            "document_id": document_id,
            "slidespeak_document_id": slidespeak_document_id,
            "filename": filename,
            "message": f"Processing {filename}..."
        },
        status="processing"
    )


async def notify_document_processing_completed(
    tenant_id: str,
    conversation_id: str,
    document_id: str,
    slidespeak_document_id: str,
    success: bool = True,
    error: Optional[str] = None
) -> bool:
    """Notify that document processing has completed"""
    return await publish_event(
        tenant_id,
        conversation_id,
        "DOCUMENT_PROCESSING_COMPLETED",
        {
            "document_id": document_id,
            "slidespeak_document_id": slidespeak_document_id,
            "success": success,
            "error": error,
            "message": "Document processed successfully!" if success else f"Processing failed: {error}"
        },
        status="completed" if success else "failed"
    )


async def notify_task_status_updated(
    tenant_id: str,
    conversation_id: str,
    task_id: str,
    status: str,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None
) -> bool:
    """Notify that task status has been updated"""
    return await publish_event(
        tenant_id,
        conversation_id,
        "TASK_STATUS_UPDATED",
        {
            "task_id": task_id,
            "status": status,
            "result": result,
            "error": error,
            "message": f"Task status: {status}"
        },
        status=status
    )


async def close_redis():
    """Close Redis connection (for shutdown)"""
    global _redis_client, _redis_pool
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
    if _redis_pool:
        await _redis_pool.disconnect()
        _redis_pool = None
        logger.info("Redis connection closed")
