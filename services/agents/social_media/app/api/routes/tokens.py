"""
Tokens router - list connected platforms, revoke token
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db_session
from app.core.auth import AuthenticatedUser, require_tenant
from app.services.db_helpers import get_tenant_tokens, delete_token

router = APIRouter()


@router.get("/v1/tokens")
async def list_tokens(
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session),
):
    """List connected platforms (platforms with stored tokens)"""
    try:
        tenant_id = user.tenant_id
        tokens = await get_tenant_tokens(session, tenant_id)
        platforms = [t.platform for t in tokens]
        return {"platforms": platforms, "count": len(platforms)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/v1/tokens/{platform}")
async def revoke_token(
    platform: str,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session),
):
    """Revoke token for a platform"""
    try:
        tenant_id = user.tenant_id
        platform = platform.lower()
        if platform not in ("tiktok", "facebook"):
            raise HTTPException(status_code=400, detail="Invalid platform")
        deleted = await delete_token(session, tenant_id, platform)
        if not deleted:
            raise HTTPException(status_code=404, detail="Token not found")
        return {"status": "revoked", "platform": platform}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
