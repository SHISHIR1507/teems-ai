"""
OAuth router - TikTok and Facebook OAuth token exchange
"""
import requests
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.core.config import get_settings
from app.core.auth import AuthenticatedUser, require_tenant
from app.services.tiktok_service import TikTokService
from app.services.facebook_service import FacebookService
from app.models.schemas import OAuthExchangeRequest

router = APIRouter()


@router.post("/v1/oauth/tiktok/exchange")
async def exchange_tiktok_code(
    request: OAuthExchangeRequest,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Exchange TikTok OAuth authorization code for access tokens.
    Called by frontend after user authorizes. Requires auth + tenant.
    """
    try:
        code = request.code
        settings = get_settings()
        
        token_url = "https://open.tiktokapis.com/v2/oauth/token/"
        payload = {
            "client_key": settings.tiktok_client_key,
            "client_secret": settings.tiktok_client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.oauth_redirect_uri,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        response = requests.post(token_url, data=payload, headers=headers, timeout=10)
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=f"Token exchange failed: {response.text}",
            )
        
        token_data = response.json()
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        tiktok_user_id = token_data.get("open_id")
        
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token in response")
        
        tenant_id = user.tenant_id
        svc = TikTokService(session, tenant_id)
        await svc.add_token(
            user_id=user.sub,
            access_token=access_token,
            refresh_token=refresh_token,
            platform_user_id=tiktok_user_id,
        )
        
        return {
            "success": True,
            "message": "Successfully connected TikTok account!",
            "platform": "tiktok",
            "platform_user_id": tiktok_user_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth exchange failed: {str(e)}")


@router.post("/v1/oauth/facebook/exchange")
async def exchange_facebook_code(
    request: OAuthExchangeRequest,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Exchange Facebook OAuth authorization code for access tokens.
    Requires auth + tenant. Requires FACEBOOK_APP_ID and FACEBOOK_APP_SECRET.
    """
    try:
        code = request.code
        settings = get_settings()
        if not settings.facebook_app_id or not settings.facebook_app_secret:
            raise HTTPException(
                status_code=503,
                detail="Facebook OAuth not configured (FACEBOOK_APP_ID, FACEBOOK_APP_SECRET)",
            )
        
        token_url = "https://graph.facebook.com/v18.0/oauth/access_token"
        params = {
            "client_id": settings.facebook_app_id,
            "client_secret": settings.facebook_app_secret,
            "code": code,
            "redirect_uri": settings.facebook_redirect_uri,
        }
        
        response = requests.get(token_url, params=params, timeout=10)
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=f"Token exchange failed: {response.text}",
            )
        
        token_data = response.json()
        access_token = token_data.get("access_token")
        
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token in response")
        
        tenant_id = user.tenant_id
        svc = FacebookService(session, tenant_id)
        await svc.add_token(
            user_id=user.sub,
            access_token=access_token,
        )
        
        return {
            "success": True,
            "message": "Successfully connected Facebook account!",
            "platform": "facebook",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth exchange failed: {str(e)}")
