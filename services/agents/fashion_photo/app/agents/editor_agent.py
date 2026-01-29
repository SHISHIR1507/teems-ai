"""
Editor Agent
Specialized for editing generated fashion images. Keeps avatar/apparel recognizable.
"""
from crewai import Agent, LLM
from app.core.config import get_settings
from app.tools.image_tools import EditFashionImageTool

settings = get_settings()
# Use OpenAI for chat/agent LLM
openai_llm = LLM(
    model=settings.llm_model,
    base_url=settings.openai_base_url,
    api_key=settings.openai_api_key,
)


def create_editor_agent() -> Agent:
    return Agent(
        role="Fashion Image Editor",
        goal="Edit generated fashion images per user request while keeping avatar and apparel recognizable",
        backstory="""You apply only the requested changes. You preserve identity and garment details.
        You use the edit_fashion_image_tool with reference images, edit instruction, and avatar/apparel URLs.
        You return all edited image URLs in your response.""",
        tools=[EditFashionImageTool()],
        verbose=True,
        allow_delegation=False,
        llm=openai_llm,
        max_iter=3,
    )
