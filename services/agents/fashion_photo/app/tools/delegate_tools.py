"""
Tools that delegate to specialist agents. Used by the Conversational Agent.
"""
import json
import re
import concurrent.futures
from crewai import Task, Crew
from crewai.tools import BaseTool
from app.core.logging import get_logger
from app.tools.vision_tools import analyze_image
from app.tools.scene_tools import validate_and_format_scene
from app.tools.image_tools import ImageGenerationTool, EditFashionImageTool
from app.agents.scene_consultant import create_scene_consultant_agent
from app.agents.image_generator_agent import create_image_generator_agent
from app.agents.editor_agent import create_editor_agent

logger = get_logger("tools.delegate")
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def _extract_json(s: str) -> str | None:
    m = re.search(r'\{[^{}]*"scene_description"[^{}]*\}', s)
    if m:
        return m.group(0)
    m = re.search(r'\{[^{}]*"urls"[^{}]*\}', s)
    if m:
        return m.group(0)
    m = re.search(r'\{[^{}]+\}', s)
    return m.group(0) if m else None


class SuggestSceneTool(BaseTool):
    """Suggests a structured scene (description + angles + variations) from apparel and avatar."""

    name: str = "suggest_scene"
    description: str = (
        "Suggest a fashion photography scene from apparel and avatar. "
        "Input: apparel_urls (JSON array of strings), avatar_urls (JSON array). "
        "Output: JSON with scene_description, angles (1–5), variations_per_angle (1–4). "
        "Prefer fewer angles/variations when enough for the look."
    )

    def _run(self, apparel_urls: str, avatar_urls: str) -> str:
        try:
            ap = json.loads(apparel_urls) if isinstance(apparel_urls, str) else apparel_urls
            av = json.loads(avatar_urls) if isinstance(avatar_urls, str) else avatar_urls
        except Exception:
            ap, av = [], []
        ap = [x for x in ap if x][:5]
        av = [x for x in av if x][:3]
        if not ap and not av:
            return json.dumps({"scene_description": "Professional fashion photography.", "angles": ["Front"], "variations_per_angle": 2})
        consultant = create_scene_consultant_agent()
        task = Task(
            description=f"""Apparel URLs: {json.dumps(ap)}. Avatar URLs: {json.dumps(av)}.
Use vision_analysis_tool with mode 'apparel' on the first apparel URL and mode 'avatar' on the first avatar URL.
Then use format_scene_suggestion with a scene_description, angles (1–5), and variations_per_angle (1–4). Prefer fewer when enough.
Return only the JSON string from format_scene_suggestion.""",
            expected_output="JSON with scene_description, angles, variations_per_angle",
            agent=consultant,
            human_input=False,
        )
        crew = Crew(agents=[consultant], tasks=[task], verbose=True, max_iter=3, full_output=False)
        try:
            out = _executor.submit(crew.kickoff).result(timeout=90)
            txt = str(out).strip()
            j = _extract_json(txt)
            if j:
                return j
        except Exception as e:
            logger.error("SuggestScene crew error: %s", e)
        app_text = analyze_image(ap[0], "apparel") if ap else ""
        av_text = analyze_image(av[0], "avatar") if av else ""
        raw = f"Apparel: {app_text}. Avatar: {av_text}."
        return validate_and_format_scene(
            "Professional fashion photography, natural lighting, clean background. " + raw,
            ["Front", "Side profile", "Three-quarter"],
            2,
        )


class GenerateImagesTool(BaseTool):
    """Generates fashion images from scene JSON and asset URLs. Delegates to Image Generator agent."""

    name: str = "generate_images"
    description: str = (
        "Generate fashion images. Input: scene_json (from suggest_scene), avatar_urls (JSON array), "
        "apparel_urls (JSON array). Output: JSON with 'urls' array. Use only after user confirmed the scene."
    )

    def _run(self, scene_json: str, avatar_urls: str, apparel_urls: str) -> str:
        try:
            sc = json.loads(scene_json) if isinstance(scene_json, str) else {}
        except Exception:
            sc = {}
        try:
            av = json.loads(avatar_urls) if isinstance(avatar_urls, str) else []
            ap = json.loads(apparel_urls) if isinstance(apparel_urls, str) else []
        except Exception:
            av, ap = [], []
        av = [x for x in av if x]
        ap = [x for x in ap if x]
        desc = sc.get("scene_description") or "Professional fashion photography."
        angles = sc.get("angles") or ["Front", "Side"]
        variations = max(1, min(4, int(sc.get("variations_per_angle", 2))))
        gen = create_image_generator_agent()
        task = Task(
            description=f"""Scene: {desc}. Angles: {json.dumps(angles)}. Variations per angle: {variations}.
Avatar URLs: {json.dumps(av)}. Apparel URLs: {json.dumps(ap)}.
Use image_generation_tool with scene_description, image_urls (avatar+apparel), angles, variations_per_angle.
Return all generated image URLs. Output a JSON object {{"urls": [...]}} with every URL.""",
            expected_output="JSON with 'urls' array of generated image URLs",
            agent=gen,
            human_input=False,
        )
        crew = Crew(agents=[gen], tasks=[task], verbose=True, max_iter=3, full_output=False)
        try:
            out = _executor.submit(crew.kickoff).result(timeout=180)
            txt = str(out).strip()
            j = _extract_json(txt) or "{}"
            obj = json.loads(j) if "{" in j else {}
            urls = obj.get("urls") or re.findall(r'https?://[^\s\'"<>\]\)]+', txt)
            return json.dumps({"urls": urls})
        except Exception as e:
            logger.error("GenerateImages crew error: %s", e)
            tool = ImageGenerationTool()
            return tool._run(desc, av + ap, angles, variations)


class EditImagesTool(BaseTool):
    """Edits fashion images per user request. Keeps avatar/apparel recognizable."""

    name: str = "edit_images"
    description: str = (
        "Edit previously generated images. Input: reference_urls (JSON array), edit_instruction (str), "
        "avatar_urls (JSON array), apparel_urls (JSON array). Returns JSON with 'urls'. Use when user asks for changes."
    )

    def _run(
        self,
        reference_urls: str,
        edit_instruction: str,
        avatar_urls: str,
        apparel_urls: str,
    ) -> str:
        try:
            ref = json.loads(reference_urls) if isinstance(reference_urls, str) else []
            av = json.loads(avatar_urls) if isinstance(avatar_urls, str) else []
            ap = json.loads(apparel_urls) if isinstance(apparel_urls, str) else []
        except Exception:
            ref, av, ap = [], [], []
        ref = [x for x in ref if x][:5]
        av = [x for x in av if x]
        ap = [x for x in ap if x]
        inst = (edit_instruction or "").strip() or "Minor refinement."
        edit_tool = EditFashionImageTool()
        return edit_tool._run(ref, inst, av, ap)
