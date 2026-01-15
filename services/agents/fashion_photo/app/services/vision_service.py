import requests
from langsmith import traceable
from app.core.config import settings

@traceable(run_type="tool", name="Get_Image_Description")
def analyze_image(image_url: str) -> str:
    """Uses GPT-4o Vision to get a description of the image content (apparel/vibes)."""
    api_key = settings.AIML_API_KEY
    url = "https://api.aimlapi.com/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe the apparel, style, and vibe of this image in 1 sentence."},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ],
        "max_tokens": 60
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        return "Visual analysis unavailable."
    except:
        return "Visual analysis error."
