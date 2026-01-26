"""
AIML LLM service
"""
import requests
from typing import List, Dict
import logging
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class AIMLLLM:
    """Service for LLM generation using AIML API"""
    
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.aiml_api_key
        self.base_url = settings.aiml_base_url
        self.model = settings.llm_model
        
        if not self.api_key:
            logger.warning("AIML_API_KEY not found. Using dummy LLM.")
            self.use_dummy = True
            return
        
        self.use_dummy = False
        logger.info(f"Using AIML LLM (model: {self.model})")
    
    async def generate(self, messages: List[Dict], model: str = None) -> str:
        if self.use_dummy:
            user_msg = messages[-1]["content"] if messages else ""
            return f"DUMMY: This is a test response to: {user_msg[:50]}..."
        
        model_to_use = model or self.model
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model_to_use,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
                verify=True
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                logger.error(f"AIML LLM Error {response.status_code}: {response.text[:200]}")
                return f"API Error {response.status_code}. Check logs."
                
        except Exception as e:
            logger.error(f"LLM Connection error: {e}", exc_info=True)
            return f"Connection error: {str(e)[:100]}"

llm = AIMLLLM()
