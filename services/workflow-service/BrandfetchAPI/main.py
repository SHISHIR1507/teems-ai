import os
from typing import Optional
from urllib.parse import urlparse
#https://businessxdata.com/

#https://open.spotify.com/



# --- 1. Load Environment Variables ---
from dotenv import load_dotenv
load_dotenv() 

import httpx
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, HttpUrl, Field

# --- 2. Initialize App ---
app = FastAPI(title="Brand Fetcher API")

# --- 3. Configuration ---
BRANDFETCH_API_KEY = os.getenv("BRANDFETCH_API_KEY")
BRANDFETCH_ENDPOINT = "https://api.brandfetch.io/v2/brands/"

# --- 4. Models ---
class CompanyRequest(BaseModel):
    url: HttpUrl = Field(..., description="The full website URL (e.g., https://www.slack.com)")

class BrandInfo(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    details: dict = {}

# --- 5. Helper Functions ---
def extract_domain(url: str) -> str:
    parsed = urlparse(str(url))
    domain = parsed.netloc
    if domain.startswith("www."):
        domain = domain[4:]
    return domain

# --- 6. Endpoints ---
@app.post("/fetch-brand", response_model=BrandInfo)
async def fetch_brand_info(request: CompanyRequest):
    domain = extract_domain(str(request.url))
    
    if not domain:
        raise HTTPException(status_code=400, detail="Invalid URL")

    if not BRANDFETCH_API_KEY:
        raise HTTPException(status_code=500, detail="API Key not found. Check .env file.")

    headers = {
        "Authorization": f"Bearer {BRANDFETCH_API_KEY}",
        "Content-Type": "application/json"
    }

    # --- FIX START: Increase timeout to 30 seconds ---
    # Default is 5s, which is too short for new websites Brandfetch hasn't scanned yet
    timeout_settings = httpx.Timeout(30.0)

    # We pass 'timeout=timeout_settings' here so the client actually waits
    async with httpx.AsyncClient(timeout=timeout_settings) as client:
    # --- FIX END ---
        try:
            print(f"DEBUG: Requesting Brandfetch for domain: {domain}")
            response = await client.get(f"{BRANDFETCH_ENDPOINT}{domain}", headers=headers)
            
            # Handle specific API errors
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Brand not found")
            elif response.status_code == 401:
                raise HTTPException(status_code=401, detail="Invalid API Key")
            elif response.status_code == 429:
                raise HTTPException(status_code=429, detail="Rate Limit Exceeded")
            
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
                detail=f"Brandfetch timed out or failed to connect: {str(e)}"
            )
        except httpx.HTTPStatusError as e:
             raise HTTPException(
                status_code=e.response.status_code, 
                detail=f"Brandfetch API Error: {e.response.text}"
            )