"""
Notification service for publishing events to Redis pub/sub
Events are consumed by the realtime workflow service and forwarded to frontend via WebSocket
"""
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from redis.asyncio import Redis
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Global Redis client (lazy initialization)
redis_client: Optional[Redis] = None


async def get_redis() -> Optional[Redis]:
    """Get or create Redis client"""
    global redis_client
    if redis_client:
        return redis_client
    
    settings = get_settings()
    redis_url = getattr(settings, 'redis_url', None)
    
    if not redis_url:
        logger.warning("REDIS_URL not configured - notifications will be disabled")
        return None
    
    try:
        redis_client = Redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        # Test connection
        await redis_client.ping()
        logger.info("✅ Redis connection established for notifications")
        return redis_client
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        return None


async def publish_notification(tenant_id: str, event_type: str, data: Dict[str, Any]) -> bool:
    """
    Publish notification to Redis channel for tenant
    
    Args:
        tenant_id: Tenant ID
        event_type: Event type (e.g., "CALENDAR_SYNC_STARTED")
        data: Event data
    
    Returns:
        True if published successfully, False otherwise
    """
    try:
        redis = await get_redis()
        if not redis:
            return False
        
        channel = f"notetaker:{tenant_id}"
        
        payload = {
            "type": event_type,
            "tenant_id": tenant_id,
            "timestamp": datetime.utcnow().isoformat(),
            **data
        }
        
        await redis.publish(channel, json.dumps(payload))
        logger.debug(f"Published notification: {event_type} to {channel}")
        return True
    
    except Exception as e:
        logger.error(f"Error publishing notification: {e}", exc_info=True)
        return False


# Convenience functions for specific event types
async def notify_calendar_sync_started(tenant_id: str, user_id: str) -> bool:
    """Notify that calendar sync has started"""
    return await publish_notification(
        tenant_id,
        "CALENDAR_SYNC_STARTED",
        {"user_id": user_id}
    )


async def notify_calendar_sync_completed(tenant_id: str, user_id: str, synced_count: int, events_with_meetings: int) -> bool:
    """Notify that calendar sync has completed"""
    return await publish_notification(
        tenant_id,
        "CALENDAR_SYNC_COMPLETED",
        {
            "user_id": user_id,
            "synced_count": synced_count,
            "events_with_meetings": events_with_meetings
        }
    )


async def notify_calendar_sync_failed(tenant_id: str, user_id: str, error: str) -> bool:
    """Notify that calendar sync has failed"""
    return await publish_notification(
        tenant_id,
        "CALENDAR_SYNC_FAILED",
        {
            "user_id": user_id,
            "error": error
        }
    )


async def notify_meeting_join_started(tenant_id: str, call_id: str, meeting_title: str, start_time: str) -> bool:
    """Notify that meeting join has started"""
    return await publish_notification(
        tenant_id,
        "MEETING_JOIN_STARTED",
        {
            "call_id": call_id,
            "meeting_title": meeting_title,
            "start_time": start_time
        }
    )


async def notify_meeting_join_completed(tenant_id: str, call_id: str, notetaker_id: str, meeting_title: str) -> bool:
    """Notify that meeting join has completed"""
    return await publish_notification(
        tenant_id,
        "MEETING_JOIN_COMPLETED",
        {
            "call_id": call_id,
            "notetaker_id": notetaker_id,
            "meeting_title": meeting_title
        }
    )


async def notify_meeting_join_failed(tenant_id: str, call_id: str, error: str) -> bool:
    """Notify that meeting join has failed"""
    return await publish_notification(
        tenant_id,
        "MEETING_JOIN_FAILED",
        {
            "call_id": call_id,
            "error": error
        }
    )


async def notify_meeting_processing_started(tenant_id: str, call_id: str, meeting_title: str) -> bool:
    """Notify that meeting processing (transcription) has started"""
    return await publish_notification(
        tenant_id,
        "MEETING_PROCESSING_STARTED",
        {
            "call_id": call_id,
            "meeting_title": meeting_title
        }
    )


async def notify_meeting_processing_completed(tenant_id: str, call_id: str, has_transcript: bool, has_summary: bool, has_action_items: bool) -> bool:
    """Notify that meeting processing has completed"""
    return await publish_notification(
        tenant_id,
        "MEETING_PROCESSING_COMPLETED",
        {
            "call_id": call_id,
            "has_transcript": has_transcript,
            "has_summary": has_summary,
            "has_action_items": has_action_items
        }
    )


async def notify_call_status_updated(tenant_id: str, call_id: str, status: str, meeting_title: str) -> bool:
    """Notify that call status has been updated"""
    return await publish_notification(
        tenant_id,
        "CALL_STATUS_UPDATED",
        {
            "call_id": call_id,
            "status": status,
            "meeting_title": meeting_title
        }
    )


async def close_redis():
    """Close Redis connection"""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None
        logger.info("Redis connection closed")
