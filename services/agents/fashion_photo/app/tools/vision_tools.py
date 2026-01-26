"""
Vision analysis tools for CrewAI agents.
Supports apparel (style, colors, textures) and avatar (build, skin, face, hair) modes.
"""
import requests
from langsmith import traceable
from crewai.tools import BaseTool
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("tools.vision")

APPAREL_PROMPT = """Describe this apparel image in 1–2 sentences. Include: style (casual/formal/sporty/etc.), colors, textures, key details, and overall aesthetic. Be precise and factual. No speculation."""

AVATAR_PROMPT = """Describe this person/avatar image in 1–2 sentences. Include: build, skin tone, face shape, hair (color, style), and any pose-relevant details. Be precise and factual. No speculation."""


@traceable(run_type="tool", name="Vision_Analysis")
def analyze_image(image_url: str, mode: str = "apparel") -> str:
    """Analyze image for apparel (style, vibe) or avatar (build, face, hair, etc.)."""
    settings = get_settings()
    url = f"{settings.aiml_base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.aiml_api_key}", "Content-Type": "application/json"}
    text = APPAREL_PROMPT if mode == "apparel" else AVATAR_PROMPT
    payload = {
        "model": settings.llm_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": text},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ],
        "max_tokens": 150,
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        out = r.json()["choices"][0]["message"]["content"]
        logger.info("Vision analysis completed mode=%s", mode)
        return out
    except requests.exceptions.RequestException as e:
        logger.error("Vision analysis error mode=%s: %s", mode, e)
        return "Visual analysis unavailable."
    except Exception as e:
        logger.error("Vision analysis error: %s", e)
        return "Visual analysis error."


class VisionAnalysisTool(BaseTool):
    name: str = "vision_analysis_tool"
    description: str = """Analyzes an image. mode: 'apparel' (style, colors, textures) or 'avatar' (build, skin, face, hair).
    Input: image_url (str), mode (str) = 'apparel' or 'avatar'.
    Returns: Short factual description."""

    def _run(self, image_url: str, mode: str = "apparel") -> str:
        if mode not in ("apparel", "avatar"):
            mode = "apparel"
        return analyze_image(image_url, mode=mode)
