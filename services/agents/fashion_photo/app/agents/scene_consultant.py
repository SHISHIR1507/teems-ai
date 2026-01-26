"""
Scene Consultant Agent
Produces structured scene: scene_description, angles (1–5), variations_per_angle (1–4).
Uses vision (apparel + avatar) and format_scene_suggestion.
"""
from crewai import Agent, LLM
from app.core.config import get_settings
from app.tools.vision_tools import VisionAnalysisTool
from app.tools.scene_tools import FormatSceneSuggestionTool

settings = get_settings()
aiml_llm = LLM(
    model=settings.llm_model,
    base_url=settings.aiml_base_url,
    api_key=settings.aiml_api_key,
)


def create_scene_consultant_agent() -> Agent:
    return Agent(
        role="Scene Consultant",
        goal="Suggest one structured fashion photography scene with angles and variations",
        backstory="""You analyze apparel and avatar, then propose a single scene. Use vision_analysis_tool
        with mode 'apparel' and 'avatar' on the given URLs. Use format_scene_suggestion with
        scene_description, angles (1–5, e.g. Front, Side, Three-quarter), and variations_per_angle (1–4).
        Prefer fewer angles/variations when the look can be achieved with less. Output only the JSON
        from format_scene_suggestion.""",
        tools=[VisionAnalysisTool(), FormatSceneSuggestionTool()],
        verbose=True,
        allow_delegation=False,
        llm=aiml_llm,
        max_iter=3,
    )
