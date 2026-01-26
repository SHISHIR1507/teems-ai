"""
Image generation tools for CrewAI agents.
Variable angles (1–5) and variations_per_angle (1–4). Identity-preserving prompts.
Uses google/nano-banana-pro-edit via AIML.
"""
import requests
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
import contextvars
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree
from crewai.tools import BaseTool
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("tools.image")

IDENTITY_GUARD = (
    "Keep the person's face, body, and skin exactly as in the reference. "
    "Keep all apparel details, colors, and shape identical to the reference. "
    "No distortion, no style transfer. Photorealistic fashion photograph only."
)
STRUCTURE_GUARD = "Single image, full frame, no collage, no grid, no split screen."


@traceable(run_type="tool", name="AIML_Image_Generation_Call")
def call_image_api(
    scene_description: str,
    image_urls: List[str],
    angle: str,
    variations: int,
) -> dict:
    """Call AIML API for one angle. variations = num_images (1–4)."""
    settings = get_settings()
    url = f"{settings.aiml_base_url}/images/generations"
    rt = get_current_run_tree()
    if rt:
        rt.add_metadata({"model": "google/nano-banana-pro-edit", "angle": angle})
    prompt = f"{angle} shot. {STRUCTURE_GUARD} {IDENTITY_GUARD} {scene_description}"
    payload = {
        "model": "google/nano-banana-pro-edit",
        "prompt": prompt,
        "image_urls": image_urls,
        "num_images": max(1, min(4, variations)),
    }
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {settings.aiml_api_key}"},
        json=payload,
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


class ImageGenerationTool(BaseTool):
    name: str = "image_generation_tool"
    description: str = (
        "Generates fashion images. Input: scene_description (str), image_urls (list of avatar+apparel URLs), "
        "angles (list of str, 1–5, e.g. ['Front', 'Side']), variations_per_angle (int 1–4). "
        "Returns: JSON string with 'urls' list."
    )

    def _run(
        self,
        scene_description: str,
        image_urls: List[str],
        angles: List[str],
        variations_per_angle: int = 2,
    ) -> str:
        import json
        if isinstance(angles, str):
            try:
                angles = json.loads(angles)
            except Exception:
                angles = [a.strip() for a in angles.split(",") if a.strip()]
        angles = [str(a).strip() for a in (angles or []) if a][:5]
        if not angles:
            angles = ["Front"]
        if isinstance(image_urls, str):
            try:
                image_urls = json.loads(image_urls)
            except Exception:
                image_urls = [u.strip() for u in image_urls.split(",") if u.strip()]
        image_urls = [u for u in (image_urls or []) if u]
        n = max(1, min(4, int(variations_per_angle)))
        all_urls = []
        errors = []
        ctx = contextvars.copy_context()

        def run(a: str):
            return ctx.run(call_image_api, scene_description, image_urls, a, n)

        with ThreadPoolExecutor(max_workers=5) as ex:
            f2a = {ex.submit(run, a): a for a in angles}
            for f in as_completed(f2a):
                ang = f2a[f]
                try:
                    data = f.result()
                    for item in data.get("data", []):
                        u = item.get("url")
                        if u:
                            all_urls.append(u)
                except Exception as e:
                    errors.append(f"{ang}: {str(e)}")
                    logger.error("%s: %s", ang, e)
        if not all_urls and errors:
            return json.dumps({"urls": [], "errors": errors})
        return json.dumps({"urls": all_urls})


EDIT_GUARD = (
    "Apply only the requested change. Keep the person and apparel recognizable. "
    "Do not alter identity or garment beyond what is needed for the edit. Photorealistic."
)


@traceable(run_type="tool", name="AIML_Edit_Call")
def call_edit_api(
    reference_image_urls: List[str],
    edit_instruction: str,
    avatar_urls: List[str],
    apparel_urls: List[str],
) -> dict:
    """Call AIML API for edit. Uses nano-banana with reference + refs."""
    settings = get_settings()
    url = f"{settings.aiml_base_url}/images/generations"
    image_urls = reference_image_urls + avatar_urls + apparel_urls
    prompt = f"{EDIT_GUARD} {edit_instruction}"
    payload = {
        "model": "google/nano-banana-pro-edit",
        "prompt": prompt,
        "image_urls": image_urls,
        "num_images": 1,
    }
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {settings.aiml_api_key}"},
        json=payload,
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


class EditFashionImageTool(BaseTool):
    name: str = "edit_fashion_image_tool"
    description: str = (
        "Edits fashion images per user request. Input: reference_image_urls (list, last generated or user choice), "
        "edit_instruction (str), avatar_urls (list), apparel_urls (list). "
        "Keeps avatar/apparel recognizable. Returns JSON with 'urls' list."
    )

    def _run(
        self,
        reference_image_urls: List[str],
        edit_instruction: str,
        avatar_urls: List[str],
        apparel_urls: List[str],
    ) -> str:
        import json
        refs = list(reference_image_urls or [])[:5]
        av = list(avatar_urls or [])
        ap = list(apparel_urls or [])
        if not refs:
            return json.dumps({"urls": [], "errors": ["No reference images"]})
        try:
            data = call_edit_api(refs, (edit_instruction or "").strip() or "Minor refinement.", av, ap)
            urls = [x.get("url") for x in data.get("data", []) if x.get("url")]
            return json.dumps({"urls": urls})
        except Exception as e:
            logger.error("Edit API error: %s", e)
            return json.dumps({"urls": [], "errors": [str(e)]})
