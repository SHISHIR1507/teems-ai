import os
import requests
import json
from typing import List, Dict
import asyncio
from dotenv import load_dotenv

load_dotenv()

class AIMLLLM:
    def __init__(self):
        self.api_key = os.getenv("AIML_API_KEY")
        self.base_url = os.getenv("AIML_BASE_URL", "https://api.aimlapi.com/v1")
        self.model = os.getenv("LLM_MODEL", "gpt-4o")
        
        if not self.api_key:
            print("⚠️ AIML_API_KEY not found. Using dummy LLM.")
            self.use_dummy = True
            return
        
        self.use_dummy = False
        print(f" Using AIML LLM (model: {self.model})")
    
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
                verify=False  # Disable SSL for testing
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                print(f" AIML LLM Error {response.status_code}: {response.text[:200]}")
                return f"API Error {response.status_code}. Check logs."
                
        except Exception as e:
            print(f" LLM Connection error: {e}")
            return f"Connection error: {str(e)[:100]}"

llm = AIMLLLM()