"""
Facebook Specialist Agent
Specialized agent for Facebook-specific operations
"""
from crewai import Agent, LLM
from app.core.config import get_settings
from app.tools.facebook_tools import post_to_facebook, get_facebook_posts

settings = get_settings()

# Configure OpenAI LLM
openai_llm = LLM(
    model=settings.llm_model,
    base_url=settings.openai_base_url,
    api_key=settings.openai_api_key
)


def create_facebook_specialist_agent() -> Agent:
    """Create the Facebook Specialist agent"""
    return Agent(
        role="Facebook Specialist",
        goal="Execute Facebook posting operations with expertise in Facebook's Graph API, page management, and video posting",
        backstory="""You are a Facebook expert who specializes in posting videos to Facebook.
        You understand:
        - Facebook's Graph API for video posting
        - Difference between posting to personal profiles vs pages
        - Facebook's video format requirements
        - How to handle page-specific posting
        
        You execute Facebook posting operations efficiently and provide clear feedback.""",
        tools=[
            post_to_facebook,
            get_facebook_posts
        ],
        verbose=True,
        allow_delegation=False,
        llm=openai_llm,
        max_iter=3
    )
