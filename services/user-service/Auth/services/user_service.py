from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.user import User
from ..models.preferences import UserPreferences
from ..schemas.preferences import (
    UserPreferencesUpdate, 
    UserPreferencesResponse,
    UserResponse
)


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_or_create_user(
        self, 
        auth0_user_id: str, 
        email: str, 
        name: str | None = None,
        tenant_id: str | None = None
    ) -> User:
        stmt = select(User).where(User.auth0_user_id == auth0_user_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user:
            if user.email != email or user.name != name or user.tenant_id != tenant_id:
                user.email = email
                user.name = name
                user.tenant_id = tenant_id
                user.updated_at = datetime.utcnow()
                self.session.add(user)
                await self.session.flush()
            return user
        
        user = User(
            auth0_user_id=auth0_user_id,
            email=email,
            name=name,
            tenant_id=tenant_id,
        )
        
        self.session.add(user)
        await self.session.flush()
        
        preferences = UserPreferences(
            user_id=user.id,
            notification_frequency="daily",
            notification_channels=["email"]
        )
        
        self.session.add(preferences)
        await self.session.flush()
        
        return user
    
    async def get_user_preferences(self, user_id: uuid.UUID) -> UserPreferencesResponse:
        stmt = select(UserPreferences).where(UserPreferences.user_id == user_id)
        result = await self.session.execute(stmt)
        preferences = result.scalar_one_or_none()
        
        if not preferences:
            preferences = UserPreferences(
                user_id=user_id,
                notification_frequency="daily",
                notification_channels=["email"]
            )
            self.session.add(preferences)
            await self.session.flush()
        
        return UserPreferencesResponse(
            user_id=preferences.user_id,
            notification_frequency=preferences.notification_frequency,
            notification_channels=preferences.notification_channels,
            created_at=preferences.created_at,
            updated_at=preferences.updated_at
        )
    
    async def update_user_preferences(
        self, 
        user_id: uuid.UUID, 
        preferences_update: UserPreferencesUpdate
    ) -> UserPreferencesResponse:
        stmt = select(UserPreferences).where(UserPreferences.user_id == user_id)
        result = await self.session.execute(stmt)
        preferences = result.scalar_one_or_none()
        
        if not preferences:
            preferences = UserPreferences(
                user_id=user_id,
                notification_frequency=preferences_update.notification_frequency,
                notification_channels=preferences_update.notification_channels
            )
        else:
            preferences.notification_frequency = preferences_update.notification_frequency
            preferences.notification_channels = preferences_update.notification_channels
            preferences.updated_at = datetime.utcnow()
        
        self.session.add(preferences)
        await self.session.flush()
        
        return UserPreferencesResponse(
            user_id=preferences.user_id,
            notification_frequency=preferences.notification_frequency,
            notification_channels=preferences.notification_channels,
            created_at=preferences.created_at,
            updated_at=preferences.updated_at
        )
    
    async def get_user_by_id(self, user_id: uuid.UUID) -> UserResponse:
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError(f"User with ID {user_id} not found")
        
        preferences = await self.get_user_preferences(user.id)
        
        return UserResponse(
            id=user.id,
            auth0_user_id=user.auth0_user_id,
            email=user.email,
            name=user.name,
            tenant_id=user.tenant_id,
            notification_frequency=preferences.notification_frequency,
            notification_channels=preferences.notification_channels,
            created_at=user.created_at,
            updated_at=user.updated_at
        )