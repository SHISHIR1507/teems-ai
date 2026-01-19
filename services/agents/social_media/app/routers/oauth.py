"""
OAuth router - TikTok OAuth token exchange
"""

import hashlib
import requests
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.config import get_settings
from app.services.tiktok_service import TikTokService

router = APIRouter()


@router.post("/oauth/tiktok/exchange")
async def exchange_tiktok_code(
    request: dict,
    db: AsyncSession = Depends(get_session)
):
    """
    Exchange TikTok OAuth authorization code for access tokens.
    Called by frontend after user authorizes.
    
    Request: {"code": "authorization_code_from_tiktok"}
    Response: {"success": true, "user_id": 123, "message": "Connected!"}
    """
    try:
        code = request.get("code")
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code required")
        
        settings = get_settings()
        
        # Exchange code for tokens
        token_url = "https://open.tiktokapis.com/v2/oauth/token/"
        
        payload = {
            "client_key": settings.tiktok_client_key,
            "client_secret": settings.tiktok_client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.oauth_redirect_uri
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        response = requests.post(token_url, data=payload, headers=headers, timeout=10)
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=400, 
                detail=f"Token exchange failed: {response.text}"
            )
        
        token_data = response.json()
        
        # Extract tokens
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        tiktok_user_id = token_data.get("open_id")
        
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token in response")
        
        # Create user_id from tiktok_user_id (consistent hash)
        user_id = int(hashlib.md5(tiktok_user_id.encode()).hexdigest()[:8], 16) % 1000000
        
        # Save to database
        service = TikTokService(db)
        # Note: The add_token method expects a TokenRequest, but OAuth exchange provides both tokens
        # This might need fixing later, but for now we'll use the TokenRequest pattern
        from app.schemas.tiktok import TokenRequest
        token_request = TokenRequest(user_id=user_id, access_token=access_token)
        await service.add_token(token_request)
        
        # TODO: Store refresh_token if the model supports it
        
        return {
            "success": True,
            "user_id": user_id,
            "message": f"Successfully connected TikTok account!",
            "tiktok_user_id": tiktok_user_id
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth exchange failed: {str(e)}")
