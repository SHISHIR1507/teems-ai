"""
Presentation Editor Agent
Specialized agent for editing presentations
"""
from crewai import Agent, LLM
from app.core.config import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL
from app.tools.editing_tools import edit_presentation, edit_slide
from app.tools.brand_tools import check_task_status

# Configure OpenAI LLM
openai_llm = LLM(
    model=LLM_MODEL,
    base_url=OPENAI_BASE_URL,
    api_key=OPENAI_API_KEY
)


def create_presentation_editor_agent() -> Agent:
    """Create the Presentation Editor agent"""
    return Agent(
        role="Presentation Editor",
        goal="Edit and modify existing PowerPoint presentations accurately",
        backstory="""You are a specialized presentation editor focused on modifying existing 
        presentations. You excel at:
        - Understanding edit requirements clearly
        - Making precise edits to presentations
        - Inserting, regenerating, or removing slides as needed
        - Tracking edit progress and confirming completion
        
        You work carefully to ensure edits are accurate and preserve presentation quality.""",
        tools=[
            edit_presentation,
            edit_slide,
            check_task_status
        ],
        verbose=True,
        allow_delegation=False,
        llm=openai_llm,
        max_iter=3
    )
