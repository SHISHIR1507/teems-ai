"""
Brand Manager Agent
Specialized agent for brand customization
"""
from crewai import Agent, LLM
from app.core.config import AIML_API_KEY, AIML_BASE_URL, LLM_MODEL
from app.tools.template_tools import get_branded_templates
from app.tools.brand_tools import get_api_credits

# Configure AIML LLM
aiml_llm = LLM(
    model=LLM_MODEL,
    base_url=AIML_BASE_URL,
    api_key=AIML_API_KEY
)


def create_brand_manager_agent() -> Agent:
    """Create the Brand Manager agent"""
    return Agent(
        role="Brand Manager",
        goal="Manage brand customization settings and ensure consistent branding across presentations",
        backstory="""You are a specialized brand manager focused on maintaining brand consistency 
        in presentations. You excel at:
        - Managing brand settings (logos, colors, fonts)
        - Applying branding to presentations
        - Ensuring brand guidelines are followed
        - Working with branded templates
        
        You help maintain a consistent brand identity across all generated presentations.""",
        tools=[
            get_branded_templates,
            get_api_credits
        ],
        verbose=True,
        allow_delegation=False,
        llm=aiml_llm,
        max_iter=3
    )
