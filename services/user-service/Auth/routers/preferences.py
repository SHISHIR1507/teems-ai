from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas.auth import AuthenticatedUser
from ..dependencies import get_current_user
from ..schemas.preferences import (
    UserPreferencesResponse,
    UserPreferencesUpdate,
)
from ..database.session import get_session
from ..services.user_service import UserService

router = APIRouter(prefix="/user", tags=["user"])


@router.get("/preferences", response_model=UserPreferencesResponse)
async def get_preferences(
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user_service = UserService(session)
    
    user = await user_service.get_or_create_user(
        auth0_user_id=current_user.sub,
        email=current_user.email or "",
        name=current_user.name,
        tenant_id=current_user.tenant_id
    )
    
    return await user_service.get_user_preferences(user.id)


@router.put("/preferences", response_model=UserPreferencesResponse)
async def update_preferences(
    preferences: UserPreferencesUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user_service = UserService(session)
    
    user = await user_service.get_or_create_user(
        auth0_user_id=current_user.sub,
        email=current_user.email or "",
        name=current_user.name,
        tenant_id=current_user.tenant_id
    )
    
    return await user_service.update_user_preferences(user.id, preferences)


