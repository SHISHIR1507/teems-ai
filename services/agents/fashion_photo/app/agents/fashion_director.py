"""
Fashion Director (Conversational Agent)
Holds all conversation. Uses delegate tools: suggest_scene, generate_images, edit_images, plus vision.
Workflow: CONVERSATION → apparel → avatar → scene → confirm → generate → editing. No manual anchors.
"""
from crewai import Agent, LLM
from app.core.config import get_settings
from app.tools.vision_tools import VisionAnalysisTool
from app.tools.delegate_tools import SuggestSceneTool, GenerateImagesTool, EditImagesTool

settings = get_settings()
aiml_llm = LLM(
    model=settings.llm_model,
    base_url=settings.aiml_base_url,
    api_key=settings.aiml_api_key,
)


def create_fashion_director_agent() -> Agent:
    return Agent(
        role="Fashion Director",
        goal="Guide users through fashion photography: apparel → avatar → scene → generate → edit. No hallucination; use only tools and context.",
        backstory="""You are an AI Creative Director for fashion photography. You hold the full conversation.
Workflow order: (1) Chat about fashion, (2) Ask for apparel uploads first, (3) Then ask for avatar, (4) Suggest a scene via suggest_scene, (5) Ask for feedback on the scene and seek confirmation naturally—do not generate until the user clearly confirms, (6) When confirmed, call generate_images, (7) After any generation or edit, ask if everything looks good or if they want changes, (8) For edits, use edit_images with reference images and the user's instruction.
You never invent URLs, scenes, or facts. Use only what tools return and what appears in the context. Respond naturally; no keyword matching or manual anchors.""",
        tools=[
            SuggestSceneTool(),
            GenerateImagesTool(),
            EditImagesTool(),
            VisionAnalysisTool(),
        ],
        verbose=True,
        allow_delegation=False,
        llm=aiml_llm,
        max_iter=8,
    )
