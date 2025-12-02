from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from jose import jwt
from jose.exceptions import JWTError

from ..config import Settings
from ..schemas.auth import AuthenticatedUser


@dataclass(slots=True)
class JWKSCache:
    keys: dict[str, Any]
    expires_at: float

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at


class Auth0Client:
    """Minimal Auth0 helper for verifying tokens and generating URLs."""

    def __init__(self, settings: Settings, jwks_ttl: int = 600) -> None:
        self.settings = settings
        self.jwks_ttl = jwks_ttl
        self._jwks_cache: JWKSCache | None = None
        self._jwks_lock = asyncio.Lock()

    @property
    def issuer(self) -> str:
        return f"https://{self.settings.auth0_domain}/"

    async def _fetch_jwks(self) -> dict[str, Any]:
        url = f"{self.issuer}.well-known/jwks.json"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def _get_jwks(self) -> dict[str, Any]:
        async with self._jwks_lock:
            if self._jwks_cache and not self._jwks_cache.expired:
                return self._jwks_cache.keys

            keys = await self._fetch_jwks()
            self._jwks_cache = JWKSCache(keys=keys, expires_at=time.time() + self.jwks_ttl)
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
        
        # EXTRACT ROLES
        roles = payload.get("https://teems.ai/roles", [])  
        if isinstance(roles, str):
            roles = [roles]
        
        if not roles:
            roles = ["normal_user"]  # Default until Auth0 provides real roles
        
        tenant_id = (
            payload.get("https://teems.ai/tenant_id") or  # Custom namespace
            payload.get("tenant_id") or                   # Standard claim
            None                                          # Default to None
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

    def build_logout_url(self, return_to: str | None = None) -> str:
        query = {"client_id": self.settings.auth0_client_id}
        if return_to:
            query["returnTo"] = return_to
        return f"{self.issuer}v2/logout?{urlencode(query)}"

