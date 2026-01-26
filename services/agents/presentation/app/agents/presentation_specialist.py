"""
Presentation Specialist Agent
Main agent that understands requirements and coordinates tasks
"""
from crewai import Agent, LLM
from app.core.config import AIML_API_KEY, AIML_BASE_URL, LLM_MODEL
from app.tools.generation_tools import (
    generate_presentation_from_text,
    generate_presentation_from_document,
    generate_presentation_slide_by_slide
)
from app.tools.editing_tools import edit_presentation, edit_slide
from app.tools.document_tools import upload_document_to_slidespeak, check_document_processing_status
from app.tools.template_tools import get_available_templates, get_branded_templates
from app.tools.brand_tools import check_task_status, get_api_credits, get_presentation_download_url

# Configure AIML LLM
aiml_llm = LLM(
    model=LLM_MODEL,
    base_url=AIML_BASE_URL,
    api_key=AIML_API_KEY
)


def create_presentation_specialist_agent() -> Agent:
    """Create the Presentation Specialist agent"""
    return Agent(
        role="Presentation Specialist",
        goal="Help users create, edit, and manage PowerPoint presentations by understanding their requirements accurately and asking clarifying questions when needed",
        backstory="""You are an expert presentation specialist with deep knowledge of presentation design, 
        content structure, and the SlideSpeak API capabilities. You excel at:
        - Understanding user requirements accurately
        - Asking clarifying questions when information is missing
        - Providing helpful suggestions based on available options
        - Never making assumptions or hallucinating - always use tools to get accurate information
        - Being friendly, professional, and patient
        
        You have access to all presentation tools and can coordinate with specialized agents when needed.
        Always confirm actions before executing them and provide clear status updates.""",
        tools=[
            generate_presentation_from_text,
            generate_presentation_from_document,
            generate_presentation_slide_by_slide,
            edit_presentation,
            edit_slide,
            upload_document_to_slidespeak,
            check_document_processing_status,
            get_available_templates,
            get_branded_templates,
            check_task_status,
            get_api_credits,
            get_presentation_download_url
        ],
        verbose=True,
        allow_delegation=True,
        llm=aiml_llm,
        max_iter=5
    )
