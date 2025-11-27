import re
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, status

from ..config import Settings


class DomainParsingError(ValueError):
    pass


class BrandfetchClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._timeout = httpx.Timeout(settings.request_timeout_seconds)

    async def fetch(self, url: str) -> dict[str, Any]:
        domain = self._extract_clean_domain(url)
        headers = {
            "Authorization": f"Bearer {self.settings.brandfetch_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.get(
                    f"{self.settings.brandfetch_endpoint}{domain}", headers=headers
                )
            except httpx.RequestError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Brandfetch unavailable: {exc}",
                ) from exc

        if response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"No brand info for '{domain}'")
        if response.status_code == 401:
            raise HTTPException(status_code=401, detail="Invalid Brandfetch token")
        if response.status_code == 429:
            raise HTTPException(
                status_code=429, detail="Brandfetch rate limit exceeded. Retry later."
            )
        if response.status_code == 422:
            raise HTTPException(
                status_code=400, detail="Brandfetch rejected this domain as invalid."
            )

        response.raise_for_status()
        data = response.json()
        data["domain"] = domain
        return data

    @staticmethod
    def _extract_clean_domain(url_input: str) -> str:
        if not url_input or not url_input.strip():
            raise DomainParsingError("URL cannot be empty")

        value = url_input.strip()
        if not value.startswith(("http://", "https://")):
            value = "https://" + value

        parsed = urlparse(value)
        domain = parsed.netloc or parsed.path.split("/")[0]

        if ":" in domain:
            domain = domain.split(":")[0]

        if domain.startswith("www."):
            domain = domain[4:]

        domain_regex = r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
        if not re.match(domain_regex, domain):
            raise DomainParsingError(f"Invalid domain format: {domain}")

        return domain.lower()

