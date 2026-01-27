"""
Realtime notification service for Fashion Photo Agent
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
from app.core.logging import get_logger

logger = get_logger("realtime_notifier")
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


def get_channel_name(tenant_id: str, session_id: str) -> str:
    """Generate Redis channel name for tenant + session"""
    return f"fashion_photo:tenant:{tenant_id}:session:{session_id}:events"


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
        event_type: Event type (SCENE_SUGGESTION_STARTED, IMAGE_GENERATION_STARTED, etc.)
        data: Event data payload
        status: Optional status (pending, processing, completed, failed)
    
    Returns:
        True if published, False otherwise (non-blocking)
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
        "timestamp": datetime.utcnow().isoformat()
    }
    
    try:
        await redis.publish(channel, json.dumps(payload))
        return True
    except Exception as e:
        # Non-blocking: log but don't raise
        logger.warning(f"⚠️  Failed to publish event to Redis: {e}")
        return False


# Convenience functions for fashion_photo events

async def notify_scene_suggestion_started(
    tenant_id: str,
    session_id: str
) -> bool:
    """Notify that scene suggestion has started"""
    return await publish_event(
        tenant_id,
        session_id,
        "SCENE_SUGGESTION_STARTED",
        {"message": "Analyzing apparel and avatar to suggest scenes..."},
        status="processing"
    )


async def notify_scene_suggestion_completed(
    tenant_id: str,
    session_id: str,
    scene_json: Dict[str, Any],
    success: bool = True,
    error: Optional[str] = None
) -> bool:
    """Notify that scene suggestion has completed"""
    return await publish_event(
        tenant_id,
        session_id,
        "SCENE_SUGGESTION_COMPLETED",
        {
            "scene": scene_json,
            "success": success,
            "error": error
        },
        status="completed" if success else "failed"
    )


async def notify_image_generation_started(
    tenant_id: str,
    session_id: str,
    batch_id: str,
    scene_description: str,
    angles_count: int,
    variations_per_angle: int
) -> bool:
    """Notify that image generation has started"""
    return await publish_event(
        tenant_id,
        session_id,
        "IMAGE_GENERATION_STARTED",
        {
            "batch_id": batch_id,
            "scene_description": scene_description,
            "angles_count": angles_count,
            "variations_per_angle": variations_per_angle,
            "message": f"Generating {angles_count * variations_per_angle} fashion images..."
        },
        status="processing"
    )


async def notify_image_generation_progress(
    tenant_id: str,
    session_id: str,
    batch_id: str,
    progress: Dict[str, Any],
    message: Optional[str] = None
) -> bool:
    """Notify image generation progress update"""
    return await publish_event(
        tenant_id,
        session_id,
        "IMAGE_GENERATION_PROGRESS",
        {
            "batch_id": batch_id,
            "progress": progress,
            "message": message
        },
        status="processing"
    )


async def notify_image_generation_completed(
    tenant_id: str,
    session_id: str,
    batch_id: str,
    image_urls: list[str],
    success: bool = True,
    error: Optional[str] = None
) -> bool:
    """Notify that image generation has completed"""
    return await publish_event(
        tenant_id,
        session_id,
        "IMAGE_GENERATION_COMPLETED",
        {
            "batch_id": batch_id,
            "image_urls": image_urls,
            "image_count": len(image_urls),
            "success": success,
            "error": error
        },
        status="completed" if success else "failed"
    )


async def notify_vision_analysis_started(
    tenant_id: str,
    session_id: str,
    asset_type: str,  # "apparel" or "avatar"
    asset_id: Optional[str] = None
) -> bool:
    """Notify that vision analysis has started"""
    return await publish_event(
        tenant_id,
        session_id,
        "VISION_ANALYSIS_STARTED",
        {
            "asset_type": asset_type,
            "asset_id": asset_id,
            "message": f"Analyzing {asset_type}..."
        },
        status="processing"
    )


async def notify_vision_analysis_completed(
    tenant_id: str,
    session_id: str,
    asset_type: str,
    success: bool = True,
    error: Optional[str] = None
) -> bool:
    """Notify that vision analysis has completed"""
    return await publish_event(
        tenant_id,
        session_id,
        "VISION_ANALYSIS_COMPLETED",
        {
            "asset_type": asset_type,
            "success": success,
            "error": error
        },
        status="completed" if success else "failed"
    )


async def notify_image_editing_started(
    tenant_id: str,
    session_id: str,
    batch_id: str,
    edit_instruction: str
) -> bool:
    """Notify that image editing has started"""
    return await publish_event(
        tenant_id,
        session_id,
        "IMAGE_EDITING_STARTED",
        {
            "batch_id": batch_id,
            "edit_instruction": edit_instruction,
            "message": "Applying edits to images..."
        },
        status="processing"
    )


async def notify_image_editing_completed(
    tenant_id: str,
    session_id: str,
    batch_id: str,
    image_urls: list[str],
    success: bool = True,
    error: Optional[str] = None
) -> bool:
    """Notify that image editing has completed"""
    return await publish_event(
        tenant_id,
        session_id,
        "IMAGE_EDITING_COMPLETED",
        {
            "batch_id": batch_id,
            "image_urls": image_urls,
            "image_count": len(image_urls),
            "success": success,
            "error": error
        },
        status="completed" if success else "failed"
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
