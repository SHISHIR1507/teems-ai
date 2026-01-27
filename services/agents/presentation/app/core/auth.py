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
    """Authenticated user from Auth0 JWT token"""

    sub: str = Field(..., description="Auth0 subject identifier")
    email: str | None = None
    name: str | None = None
    permissions: list[str] = Field(default_factory=list)
    scope: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    tenant_id: str | None = Field(None, description="User's tenant identifier")
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
    """Auth0 helper for verifying JWT tokens"""

    def __init__(self, settings: Settings, jwks_ttl: int = 600) -> None:
        self.settings = settings
        self.jwks_ttl = jwks_ttl
        self._jwks_cache: JWKSCache | None = None
        self._jwks_lock = None  # lazily created asyncio.Lock

    @property
    def issuer(self) -> str:
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

        permissions = payload.get("permissions") or []
        scope_claim = payload.get("scope") or []
        if isinstance(scope_claim, str):
            scope = scope_claim.split()
        else:
            scope = scope_claim

        expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

        roles = payload.get("https://teems.ai/roles", [])  # custom namespace
        if isinstance(roles, str):
            roles = [roles]
        if not roles:
            roles = ["normal_user"]

        tenant_id = (
            payload.get("https://teems.ai/tenant_id")  # preferred custom claim
            or payload.get("tenant_id")  # fallback
            or None
        )

        return AuthenticatedUser(
            sub=payload["sub"],
            email=payload.get("email"),
            name=payload.get("name"),
            permissions=list(permissions),
            scope=list(scope),
            roles=roles,
            tenant_id=tenant_id,
            expires_at=expires_at,
        )


def get_auth0_client(settings: Settings = Depends(get_settings)) -> Auth0Client:
    """Get or create Auth0 client instance"""
    return Auth0Client(settings=settings)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    client: Auth0Client = Depends(get_auth0_client),
) -> AuthenticatedUser:
    """Dependency to get current authenticated user"""
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
    """
    Dependency that enforces presence of tenant_id in the authenticated user.
    
    IMPORTANT: Token validation happens ONCE at request start via FastAPI dependency injection.
    The token is validated when this dependency is resolved (before the route handler executes).
    For long-running operations (e.g., presentation generation, document processing), the token
    is NOT re-validated during execution. This allows operations to complete even if the token
    expires mid-execution, as long as it was valid when the request started.
    
    This is the intended behavior to prevent long-running operations from failing due to token
    expiration during execution.
    """

    async def tenant_checker(user: AuthenticatedUser = Depends(get_current_user)):
        if not user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have a tenant assigned",
            )
        return user

    return tenant_checker
