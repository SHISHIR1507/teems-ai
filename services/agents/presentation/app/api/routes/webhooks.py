"""
Webhook endpoints for SlideSpeak notifications
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db_session
from app.core.auth import AuthenticatedUser, require_tenant, get_current_user
from app.services.webhook_service import process_webhook

router = APIRouter()


@router.post("/v1/webhooks/slidespeak", tags=["webhooks"])
async def receive_slidespeak_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Receive webhook notifications from SlideSpeak.
    
    This endpoint processes async task completion notifications.
    No authentication required (external service callback).
    """
    try:
        # Get webhook payload as dict
        webhook_data = await request.json()
        # Process webhook
        result = await process_webhook(session, webhook_data)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/webhooks/subscribe", tags=["webhooks"])
async def subscribe_webhook(
    webhook_url: str = None,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Subscribe to SlideSpeak webhooks (if webhook_url provided).
    Otherwise, return current subscription status.
    Requires tenant.
    """
    try:
        from app.services.slidespeak_client import get_slidespeak_client
        from app.core.config import WEBHOOK_BASE_URL
        
        client = get_slidespeak_client()
        
        if webhook_url:
            # Subscribe with provided URL
            result = client.subscribe_webhook(webhook_url)
            return {"status": "subscribed", "webhook_url": webhook_url, "result": result}
        else:
            # Return default webhook URL (for info)
            default_url = f"{WEBHOOK_BASE_URL}/v1/webhooks/slidespeak"
            return {
                "status": "info",
                "webhook_url": default_url,
                "message": "Use this URL to subscribe in SlideSpeak dashboard"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
