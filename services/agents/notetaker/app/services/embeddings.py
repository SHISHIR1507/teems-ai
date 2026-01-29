"""
OpenAI Embeddings service
"""
from typing import List
import requests
import logging
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class OpenAIEmbedder:
    """Service for generating embeddings using OpenAI API"""
    
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.openai_api_key
        self.base_url = settings.openai_base_url
        self.model = settings.embedding_model
        
        if not self.api_key:
            logger.warning("OPENAI_API_KEY not found. Using dummy embeddings.")
            self.use_dummy = True
            return
        
        self.use_dummy = False
        provider = "OpenAI" if "openai.com" in self.base_url else "AIML" if "aimlapi" in self.base_url else "Unknown"
        logger.info(f"Using {provider} embeddings (model: {self.model})")
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        if self.use_dummy or not texts:
            logger.debug("Using dummy embeddings")
            return [[0.1] * 1536 for _ in texts]
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "input": texts,
            "encoding_format": "float"
        }
        
        try:
            provider = "OpenAI" if "openai.com" in self.base_url else "AIML" if "aimlapi" in self.base_url else "Unknown"
            logger.info(f"🔗 Embeddings using: {provider} | URL: {self.base_url} | Key: {self.api_key[:12]}...")
            logger.info(f"Requesting embeddings for {len(texts)} chunks...")
            
            response = requests.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json=payload,
                timeout=10,
                verify=True
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                embeddings = [item["embedding"] for item in data["data"]]
                logger.info(f"Got {len(embeddings)} embeddings ({len(embeddings[0]) if embeddings else 0} dimensions)")
                return embeddings
            else:
                logger.error(f"OpenAI API Error {response.status_code}: {response.text[:200]}")
                return [[0.1] * 1536 for _ in texts]
                
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}", exc_info=True)
            return [[0.1] * 1536 for _ in texts]
    
    async def embed_one(self, text: str) -> List[float]:
        embeddings = await self.embed([text])
        return embeddings[0] if embeddings else [0.1] * 1536

embedder = OpenAIEmbedder()

