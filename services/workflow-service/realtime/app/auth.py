from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JWTError
from pydantic import BaseModel, Field

from .config import Settings, get_settings


bearer_scheme = HTTPBearer(auto_error=False)


class AuthenticatedUser(BaseModel):
    sub: str = Field(..., description="Auth0 subject identifier")
    tenant_id: str | None = None
    roles: list[str] = Field(default_factory=list)
    expires_at: datetime


@dataclass(slots=True)
class JWKSCache:
    keys: dict[str, Any]
    expires_at: float

    @property
    def expired(self) -> bool:
        from time import time as _time

        return _time() >= self.expires_at


class Auth0Client:
    def __init__(self, settings: Settings, jwks_ttl: int = 600) -> None:
        self.settings = settings
        self.jwks_ttl = jwks_ttl
        self._jwks_cache: JWKSCache | None = None
        self._jwks_lock = None

    @property
    def issuer(self) -> str:
        assert self.settings.auth0_domain
        return f"https://{self.settings.auth0_domain}/"

    async def _ensure_lock(self):
        if self._jwks_lock is None:
            import asyncio

            self._jwks_lock = asyncio.Lock()

    async def _fetch_jwks(self) -> dict[str, Any]:
        url = f"{self.issuer}.well-known/jwks.json"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def _get_jwks(self) -> dict[str, Any]:
        await self._ensure_lock()
        assert self._jwks_lock is not None
        async with self._jwks_lock:
            from time import time as _time

            if self._jwks_cache and not self._jwks_cache.expired:
                return self._jwks_cache.keys

            keys = await self._fetch_jwks()
            self._jwks_cache = JWKSCache(keys=keys, expires_at=_time() + self.jwks_ttl)
            return keys

    async def verify_access_token(self, token: str) -> AuthenticatedUser:
        if not self.settings.auth0_domain or not self.settings.auth0_audience:
            raise ValueError("Auth0 settings not configured")

        jwks = await self._get_jwks()
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if kid is None:
            raise ValueError("Token missing key id (kid)")

        rsa_key = next((key for key in jwks["keys"] if key.get("kid") == kid), None)
        if rsa_key is None:
            raise ValueError("Unable to find matching key")

        try:
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=[self.settings.auth0_algorithm],
                audience=self.settings.auth0_audience,
                issuer=self.issuer,
            )
        except JWTError as exc:
            raise ValueError(f"Token validation failed: {exc}") from exc

        roles = payload.get("https://teems.ai/roles", [])
        if isinstance(roles, str):
            roles = [roles]
        if not roles:
            roles = ["normal_user"]

        tenant_id = (
            payload.get("https://teems.ai/tenant_id")
            or payload.get("tenant_id")
            or None
        )

        return AuthenticatedUser(
            sub=payload["sub"],
            tenant_id=tenant_id,
            roles=roles,
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        )


def get_auth0_client(settings: Settings = Depends(get_settings)) -> Auth0Client:
    return Auth0Client(settings=settings)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    client: Auth0Client = Depends(get_auth0_client),
) -> AuthenticatedUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
    token = credentials.credentials
    try:
        return await client.verify_access_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


def require_tenant():
    async def tenant_checker(user: AuthenticatedUser = Depends(get_current_user)):
        if not user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have a tenant assigned",
            )
        return user

    return tenant_checker


async def authenticate_websocket(
    websocket: "WebSocket",
    client: Auth0Client,
    timeout_seconds: float = 10.0,
    require_tenant_id: bool = True,
) -> AuthenticatedUser | None:
    """
    Authenticate a WebSocket connection using first-message auth pattern.
    
    The client must send {"action": "auth", "token": "<JWT>"} as the first message.
    
    Args:
        websocket: The WebSocket connection (must be already accepted)
        client: Auth0Client instance for token validation
        timeout_seconds: How long to wait for auth message before closing
        require_tenant_id: If True, reject users without tenant_id
        
    Returns:
        AuthenticatedUser on success, None on failure (socket will be closed)
    """
    import asyncio
    from loguru import logger
    
    try:
        # Wait for auth message with timeout
        try:
            message = await asyncio.wait_for(
                websocket.receive_json(),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.warning("WebSocket auth timeout - no auth message received")
            await websocket.send_json({
                "type": "AUTH_FAILED",
                "error": f"Authentication timeout - send auth message within {int(timeout_seconds)} seconds"
            })
            await websocket.close(code=4001)
            return None
        
        # Validate message format
        action = message.get("action")
        if action != "auth":
            logger.warning("WebSocket first message was not auth: {}", action)
            await websocket.send_json({
                "type": "AUTH_FAILED",
                "error": "First message must be auth action"
            })
            await websocket.close(code=4002)
            return None
        
        token = message.get("token")
        if not token:
            logger.warning("WebSocket auth message missing token")
            await websocket.send_json({
                "type": "AUTH_FAILED",
                "error": "Token is required"
            })
            await websocket.close(code=4003)
            return None
        
        # Validate token with Auth0
        try:
            user = await client.verify_access_token(token)
        except ValueError as exc:
            logger.warning("WebSocket auth failed: {}", exc)
            await websocket.send_json({
                "type": "AUTH_FAILED",
                "error": str(exc)
            })
            await websocket.close(code=4004)
            return None
        
        # Check tenant_id if required
        if require_tenant_id and not user.tenant_id:
            logger.warning("WebSocket auth rejected - user {} has no tenant_id", user.sub)
            await websocket.send_json({
                "type": "AUTH_FAILED", 
                "error": "User does not have a tenant assigned"
            })
            await websocket.close(code=4005)
            return None
        
        # Success!
        logger.info("WebSocket authenticated: user={}, tenant={}", user.sub, user.tenant_id)
        await websocket.send_json({
            "type": "AUTH_SUCCESS",
            "user": user.sub,
            "tenant_id": user.tenant_id,
        })
        return user
        
    except Exception as exc:
        logger.exception("Unexpected error during WebSocket auth: {}", exc)
        try:
            await websocket.send_json({
                "type": "AUTH_FAILED",
                "error": "Internal authentication error"
            })
            await websocket.close(code=1011)
        except Exception:
            pass
        return None
