import os
import re
from typing import Optional
from urllib.parse import urlparse

# --- 1. Load Environment Variables ---
from dotenv import load_dotenv
load_dotenv() 

import httpx
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, validator

# --- 2. Initialize App ---
app = FastAPI(title="Brand Fetcher API")

# --- 3. Configuration ---
BRANDFETCH_API_KEY = os.getenv("BRANDFETCH_API_KEY")
BRANDFETCH_ENDPOINT = "https://api.brandfetch.io/v2/brands/"

# --- 4. Models ---
class CompanyRequest(BaseModel):
    # Changed from HttpUrl to str so we can accept "google.com" without http:// and fix it ourselves
    url: str = Field(..., description="The website URL (e.g. 'slack.com' or 'https://slack.com')")

    @validator('url')
    def validate_url_structure(cls, v):
        if not v or not v.strip():
            raise ValueError('URL cannot be empty')
        return v.strip()

class BrandInfo(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    details: dict = {}

# --- 5. Helper Functions (Enhanced) ---
def extract_clean_domain(url_input: str) -> Optional[str]:
    """
    Robustly extracts a domain from messy inputs.
    Handles: "google.com", "https://google.com/foo", "google.com:8080"
    """
    try:
        # Step A: Handle missing schema (common user error)
        # If user types "spotify.com", urlparse sees it as a 'path', not a 'netloc'.
        if not url_input.startswith("http://") and not url_input.startswith("https://"):
            url_input = "https://" + url_input

        parsed = urlparse(url_input)
        domain = parsed.netloc

        # Step B: Fallback if netloc is empty (rare, but happens with some malformed strings)
        if not domain and parsed.path:
            domain = parsed.path.split("/")[0]

        # Step C: Cleaning
        # 1. Remove port numbers (e.g. google.com:443 -> google.com)
        if ":" in domain:
            domain = domain.split(":")[0]
        
        # 2. Remove 'www.' prefix
        if domain.startswith("www."):
            domain = domain[4:]

        # Step D: Regex Validation
        # Ensures it looks like a domain (something.something) and not just "localhost" or "test"
        # This regex matches: alphanumeric+hyphens . alphanumeric (2+ chars)
        domain_regex = r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
        
        if not re.match(domain_regex, domain):
            print(f"DEBUG: Domain '{domain}' failed regex validation")
            return None

        return domain.lower() # Normalize to lowercase

    except Exception as e:
        print(f"DEBUG: Parsing error for input '{url_input}': {e}")
        return None

# --- 6. Endpoints ---
@app.post("/fetch-brand", response_model=BrandInfo)
async def fetch_brand_info(request: CompanyRequest):
    # 1. Extract and Validate Domain
    domain = extract_clean_domain(request.url)
    
    # Edge Case Catching: Invalid Domain Format
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid URL format. Could not extract a valid domain (e.g., 'example.com')."
        )

    # Edge Case Catching: Missing API Key
    if not BRANDFETCH_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Server Misconfiguration: API Key not found."
        )

    headers = {
        "Authorization": f"Bearer {BRANDFETCH_API_KEY}",
        "Content-Type": "application/json"
    }

    # 2. Call API with Extended Timeout
    timeout_settings = httpx.Timeout(30.0)

    async with httpx.AsyncClient(timeout=timeout_settings) as client:
        try:
            print(f"DEBUG: Fetching data for domain: {domain}")
            response = await client.get(f"{BRANDFETCH_ENDPOINT}{domain}", headers=headers)
            
            # Edge Case Catching: API Specific Errors
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Brand information not found for '{domain}'")
            elif response.status_code == 401:
                raise HTTPException(status_code=401, detail="Invalid Brandfetch API Key.")
            elif response.status_code == 429:
                raise HTTPException(status_code=429, detail="Rate Limit Exceeded. Please try again later.")
            elif response.status_code == 422:
                # Brandfetch sometimes returns 422 for unprocessable domains
                raise HTTPException(status_code=400, detail="Brandfetch rejected this domain as invalid.")
            
            response.raise_for_status()
            
            data = response.json()
            
            return BrandInfo(
                name=data.get("name"),
                domain=data.get("domain"),
                icon=data.get("icon"),
                description=data.get("description"),
                details=data
            )

        except httpx.RequestError as e:
            print(f"CONNECTION ERROR: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
                detail=f"External service unreachable: {str(e)}"
            )
        except httpx.HTTPStatusError as e:
             # Handles 500 errors from Brandfetch side
             raise HTTPException(
                status_code=e.response.status_code, 
                detail=f"Brandfetch API Error: {e.response.text}"
            )