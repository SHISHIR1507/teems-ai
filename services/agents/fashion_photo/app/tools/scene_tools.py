"""
Scene suggestion tools. Structured output: scene_description, angles (1–5), variations_per_angle (1–4).
"""
import json
from crewai.tools import BaseTool
from app.core.logging import get_logger

logger = get_logger("tools.scene")


def validate_and_format_scene(
    scene_description: str,
    angles: list[str],
    variations_per_angle: int
) -> str:
    """Validate inputs and return JSON. angles 1–5, variations 1–4."""
    if isinstance(angles, str):
        try:
            angles = json.loads(angles)
        except Exception:
            angles = [a.strip() for a in angles.split(",") if a.strip()]
    angles = [str(a).strip() for a in (angles or []) if a][:5]
    if not angles:
        angles = ["Front"]
    n = max(1, min(4, int(variations_per_angle) if isinstance(variations_per_angle, int) else 2))
    desc = (scene_description or "").strip() or "Professional fashion photography scene"
    out = {
        "scene_description": desc,
        "angles": angles,
        "variations_per_angle": n,
    }
    return json.dumps(out)


class FormatSceneSuggestionTool(BaseTool):
    name: str = "format_scene_suggestion"
    description: str = """Validates and formats a scene suggestion. Use after you have decided scene, angles, and variations.
    Input: scene_description (str), angles (list of str, 1–5 items), variations_per_angle (int, 1–4).
    Returns: JSON string with scene_description, angles, variations_per_angle."""

    def _run(
        self,
        scene_description: str,
        angles: list[str],
        variations_per_angle: int = 2
    ) -> str:
        return validate_and_format_scene(scene_description, angles, variations_per_angle)
