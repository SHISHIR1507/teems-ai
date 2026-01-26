"""
Image Generator Agent
Generates fashion images from structured scene + assets. Variable angles and variations.
"""
from crewai import Agent, LLM
from app.core.config import get_settings
from app.tools.image_tools import ImageGenerationTool

settings = get_settings()
aiml_llm = LLM(
    model=settings.llm_model,
    base_url=settings.aiml_base_url,
    api_key=settings.aiml_api_key,
)


def create_image_generator_agent() -> Agent:
    return Agent(
        role="Image Generator",
        goal="Generate fashion images from scene JSON and asset URLs",
        backstory="""You use image_generation_tool with scene_description, image_urls (avatar+apparel),
        angles (from scene JSON), and variations_per_angle. You return all generated URLs. You never
        distort avatar or apparel.""",
        tools=[ImageGenerationTool()],
        verbose=True,
        allow_delegation=False,
        llm=aiml_llm,
        max_iter=3,
    )
