"""
Presentation Generator Agent
Specialized agent for presentation generation
"""
from crewai import Agent, LLM
from app.core.config import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL
from app.tools.generation_tools import (
    generate_presentation_from_text,
    generate_presentation_from_document,
    generate_presentation_slide_by_slide
)
from app.tools.template_tools import get_available_templates, get_branded_templates
from app.tools.brand_tools import check_task_status

# Configure OpenAI LLM
openai_llm = LLM(
    model=LLM_MODEL,
    base_url=OPENAI_BASE_URL,
    api_key=OPENAI_API_KEY
)


def create_presentation_generator_agent() -> Agent:
    """Create the Presentation Generator agent"""
    return Agent(
        role="Presentation Generator",
        goal="Generate PowerPoint presentations efficiently using the SlideSpeak API",
        backstory="""You are a specialized presentation generator focused on creating high-quality 
        PowerPoint presentations. You excel at:
        - Executing presentation generation tasks accurately
        - Using the right generation method (text, document, or slide-by-slide)
        - Applying appropriate templates and settings
        - Tracking generation progress and providing updates
        
        You work efficiently and follow instructions precisely from the Presentation Specialist.""",
        tools=[
            generate_presentation_from_text,
            generate_presentation_from_document,
            generate_presentation_slide_by_slide,
            get_available_templates,
            get_branded_templates,
            check_task_status
        ],
        verbose=True,
        allow_delegation=False,
        llm=openai_llm,
        max_iter=3
    )
