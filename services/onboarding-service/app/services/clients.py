import json
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, status

from ..config import Settings


class DomainParsingError(ValueError):
    pass


class BrandfetchClient:
    """Client for calling Brandfetch API service."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.brandfetch_api_url
        self._timeout = httpx.Timeout(30.0)
        # Reuse HTTP client with connection pooling for high concurrency
        self._client = httpx.AsyncClient(
            timeout=self._timeout,
            limits=httpx.Limits(
                max_connections=100,  # Max concurrent connections
                max_keepalive_connections=20,  # Keep-alive connections
            ),
        )

    @staticmethod
    def validate_url(url_input: str) -> tuple[bool, str | None]:
        """
        Validate URL format. Returns (is_valid, error_message).
        Similar to BrandfetchClient._extract_clean_domain but returns validation result.
        """
        if not url_input or not url_input.strip():
            return False, "URL cannot be empty"

        value = url_input.strip()
        if not value.startswith(("http://", "https://")):
            value = "https://" + value

        try:
            parsed = urlparse(value)
            domain = parsed.netloc or parsed.path.split("/")[0]

            if ":" in domain:
                domain = domain.split(":")[0]

            if domain.startswith("www."):
                domain = domain[4:]

            domain_regex = r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
            if not re.match(domain_regex, domain):
                return False, f"Invalid domain format: {domain}"

            return True, None
        except Exception as e:
            return False, f"Invalid URL format: {str(e)}"

    async def fetch_brand(
        self, 
        url: str, 
        conversation_id: str | None = None, 
        tenant_id: str | None = None,
        auth_token: str | None = None
    ) -> dict[str, Any]:
        """Call Brandfetch API to fetch brand information."""
        headers = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        
        try:
            response = await self._client.post(
                f"{self.base_url}/brands/fetch",
                json={
                    "url": url,
                    "force_refresh": False,
                    "conversation_id": conversation_id,
                    "tenant_id": tenant_id,
                },
                headers=headers,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                error_detail = e.response.json().get("detail", "Invalid URL")
                raise HTTPException(status_code=400, detail=error_detail)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Brandfetch API unavailable: {e}",
            )
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Brandfetch unavailable: {exc}",
            ) from exc

    async def close(self):
        """Close the HTTP client (call during shutdown)."""
        await self._client.aclose()

