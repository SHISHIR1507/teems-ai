from typing import List
import requests
from app.core.config import settings

class AIMLEmbedder:
    def __init__(self):
        self.api_key = settings.AIML_API_KEY
        self.base_url = settings.AIML_BASE_URL
        self.model = settings.EMBEDDING_MODEL
        
        if not self.api_key:
            print("⚠️ AIML_API_KEY not found. Using dummy embeddings.")
            self.use_dummy = True
            return
        
        self.use_dummy = False
        print(f"✅ Using AIML embeddings (model: {self.model})")
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        if self.use_dummy or not texts:
            print("Using dummy embeddings")
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
            print(f"Requesting embeddings for {len(texts)} chunks...")
            
            response = requests.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json=payload,
                timeout=10,
                verify=True  # Enable SSL verification
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                embeddings = [item["embedding"] for item in data["data"]]
                print(f"✅ Got {len(embeddings)} embeddings ({len(embeddings[0])} dimensions)")
                return embeddings
            else:
                print(f"⚠️ AIML API Error {response.status_code}: {response.text[:200]}")
                return [[0.1] * 1536 for _ in texts]
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return [[0.1] * 1536 for _ in texts]
    
    async def embed_one(self, text: str) -> List[float]:
        embeddings = await self.embed([text])
        return embeddings[0] if embeddings else [0.1] * 1536

embedder = AIMLEmbedder()
