"""
Vision analysis tools for social media content (images and videos).
Uses GPT-4o Vision API to analyze content for caption/hashtag suggestions.
"""
import requests
from app.core.config import get_settings

CONTENT_PROMPT = """Analyze this image/video for social media posting. Describe what you see in 2-3 sentences. Include: main subject, setting/scene, mood/vibe, colors, key visual elements, and any text or notable details. Be specific and factual. Focus on elements that would help create engaging captions and relevant hashtags."""


def analyze_content(content_url: str, asset_type: str = "image") -> str:
    """
    Analyze image or video content using GPT-4o Vision API.
    
    Args:
        content_url: Public URL of the image or video (must be accessible)
        asset_type: 'image' or 'video'
    
    Returns:
        Vision analysis description (2-3 sentences)
    """
    settings = get_settings()
    url = f"{settings.aiml_base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.aiml_api_key}", "Content-Type": "application/json"}
    
    # For videos, we analyze as image (most vision APIs can handle video URLs or first frame)
    # If the API doesn't support video, we'll get an error and handle gracefully
    payload = {
        "model": settings.llm_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": CONTENT_PROMPT},
                    {"type": "image_url", "image_url": {"url": content_url}},
                ],
            }
        ],
        "max_tokens": 300,
    }
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        out = r.json()["choices"][0]["message"]["content"]
        return out
    except requests.exceptions.RequestException as e:
        # If video URL doesn't work with vision API, return a generic message
        if asset_type == "video":
            return "Video content detected. Visual analysis may be limited for videos."
        return f"Visual analysis unavailable: {str(e)}"
    except Exception as e:
        return f"Visual analysis error: {str(e)}"
