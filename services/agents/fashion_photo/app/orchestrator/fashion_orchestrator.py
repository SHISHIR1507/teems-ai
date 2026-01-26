"""
Fashion Orchestrator
Chat-only flow. All conversation through Fashion Director with full context. No manual anchors.
Programmatic endpoints (scenes, images) use suggest_scenes_orchestrated / generate_images_orchestrated.
"""
import json
import re
from crewai import Task, Crew
from app.agents.fashion_director import create_fashion_director_agent
from app.agents.scene_consultant import create_scene_consultant_agent
from app.agents.image_generator_agent import create_image_generator_agent
from app.tools.vision_tools import analyze_image
from app.tools.scene_tools import validate_and_format_scene
from app.tools.image_tools import ImageGenerationTool
from typing import Optional, Dict, Any, List
import concurrent.futures
from app.core.logging import get_logger

logger = get_logger("orchestrator")
executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)


def chat_with_fashion_director(
    message: str,
    stage: str,
    avatars: List[str],
    apparel: List[str],
    generated_images: List[str],
    history_text: str = "",
    visual_context: str = "",
    suggested_scene: Optional[Dict[str, Any]] = None,
    last_batch_urls: Optional[List[str]] = None,
) -> str:
    """
    Single entry point for chat. Fashion Director holds the conversation.
    Uses delegate tools (suggest_scene, generate_images, edit_images) + vision.
    """
    agent = create_fashion_director_agent()
    last_urls = last_batch_urls or []
    scene_note = ""
    if suggested_scene:
        scene_note = f"\nSuggested scene (from earlier turn): {suggested_scene}. Use it when user confirms."

    context = f"""
Current stage: {stage}

Assets:
- Avatar URLs: {avatars}
- Apparel URLs: {apparel}
- Last generated batch URLs: {last_urls}
- Total generated so far: {len(generated_images)} images
{scene_note}

{visual_context}

Workflow: (1) Apparel first, then avatar. (2) Suggest scene via suggest_scene when you have both. (3) Ask for feedback and confirmation naturally—do not generate until user clearly confirms. (4) After generation or edit, ask if everything looks good or if they want changes. (5) For edits use edit_images with reference_urls (last batch), edit_instruction, avatar_urls, apparel_urls.
When you include generated image URLs in your reply, list each URL on its own line. Do not truncate or hide them.
"""

    task_desc = f"""
HISTORY:
{history_text}

CURRENT USER MESSAGE: {message}

{context}

Respond naturally. Use tools when appropriate. Never hallucinate URLs or scene details.
"""
    task = Task(
        description=task_desc,
        expected_output="Helpful reply, optionally including generated image URLs.",
        agent=agent,
        human_input=False,
    )
    crew = Crew(agents=[agent], tasks=[task], verbose=True, max_iter=8, full_output=False)
    try:
        future = executor.submit(crew.kickoff)
        result = future.result(timeout=180)
        return str(result)
    except concurrent.futures.TimeoutError:
        logger.error("Chat request timed out")
        return "Sorry, that took too long. Please try again."
    except Exception as e:
        logger.error("Chat error: %s", e)
        return f"Sorry, I ran into an error: {str(e)}"


def suggest_scenes_orchestrated(
    apparel_urls: List[str],
    avatar_urls: Optional[List[str]] = None,
    visual_analysis: Optional[str] = None,
) -> Dict[str, Any]:
    """Structured scene suggestion for /v1/scenes/suggest. Returns scene_description, angles, variations."""
    av = avatar_urls or []
    ap = list(apparel_urls or [])[:5]
    av = list(av)[:3]
    if not ap and not av:
        out = validate_and_format_scene("Professional fashion photography.", ["Front"], 2)
        try:
            sc = json.loads(out)
        except Exception:
            sc = {"scene_description": "Professional fashion photography.", "angles": ["Front"], "variations_per_angle": 2}
        return {"scenes": [sc.get("scene_description", "")], "scene_json": sc, "message": out, "status": "success"}
    consultant = create_scene_consultant_agent()
    task = Task(
        description=f"""Apparel URLs: {json.dumps(ap)}. Avatar URLs: {json.dumps(av)}.
Use vision_analysis_tool (apparel, then avatar). Use format_scene_suggestion. Return only the JSON.""",
        expected_output="JSON with scene_description, angles, variations_per_angle",
        agent=consultant,
        human_input=False,
    )
    crew = Crew(agents=[consultant], tasks=[task], verbose=True, max_iter=3, full_output=False)
    try:
        raw = executor.submit(crew.kickoff).result(timeout=90)
        txt = str(raw).strip()
        start = txt.find("{")
        j = None
        if start >= 0:
            depth = 0
            for i, c in enumerate(txt[start:], start):
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        j = txt[start : i + 1]
                        break
        if j:
            sc = json.loads(j)
        else:
            app_text = analyze_image(ap[0], "apparel") if ap else ""
            av_text = analyze_image(av[0], "avatar") if av else ""
            raw2 = f"Apparel: {app_text}. Avatar: {av_text}."
            out = validate_and_format_scene("Professional fashion, natural lighting. " + raw2, ["Front", "Side"], 2)
            sc = json.loads(out)
        desc = sc.get("scene_description", "")
        return {"scenes": [desc], "scene_json": sc, "message": json.dumps(sc), "status": "success"}
    except Exception as e:
        logger.error("Suggest scenes error: %s", e)
        return {"scenes": [], "scene_json": {}, "message": str(e), "status": "failed"}


def generate_images_orchestrated(
    scene_description: str,
    avatar_urls: List[str],
    apparel_urls: List[str],
    scene_json: Optional[Dict[str, Any]] = None,
    previous_images: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Image generation for /v1/images/generate. Uses variable angles/variations."""
    sc = scene_json or {}
    desc = sc.get("scene_description") or scene_description or "Professional fashion photography."
    angles = sc.get("angles") or ["Front", "Side"]
    variations = max(1, min(4, int(sc.get("variations_per_angle", 2))))
    urls = list(avatar_urls or []) + list(apparel_urls or [])
    if previous_images:
        urls.extend(previous_images)
    tool = ImageGenerationTool()
    try:
        out = tool._run(desc, urls, angles, variations)
        data = json.loads(out) if isinstance(out, str) and out.strip().startswith("{") else {}
        urls_out = data.get("urls") or re.findall(r'https?://[^\s\'"<>\]\)]+', str(out))
        return {"image_urls": urls_out, "message": out, "status": "success" if urls_out else "failed"}
    except Exception as e:
        logger.error("Generate images error: %s", e)
        return {"image_urls": [], "message": str(e), "status": "failed"}
