"""
TikTok Specialist Agent
Specialized agent for TikTok-specific operations
"""
from crewai import Agent, LLM
from app.core.config import get_settings
from app.tools.tiktok_tools import post_to_tiktok, get_tiktok_posts, refresh_tiktok_token

settings = get_settings()

# Configure OpenAI LLM
openai_llm = LLM(
    model=settings.llm_model,
    base_url=settings.openai_base_url,
    api_key=settings.openai_api_key
)


def create_tiktok_specialist_agent() -> Agent:
    """Create the TikTok Specialist agent"""
    return Agent(
        role="TikTok Specialist",
        goal="Execute TikTok posting operations with expertise in TikTok-specific features like hashtags, captions, and video optimization",
        backstory="""You are a TikTok expert who specializes in posting videos to TikTok.
        You understand:
        - TikTok's video format requirements
        - How to optimize captions and hashtags for TikTok
        - TikTok's privacy settings and posting options
        - How to handle token refresh when needed
        
        You execute TikTok posting operations efficiently and provide clear feedback.""",
        tools=[
            post_to_tiktok,
            get_tiktok_posts,
            refresh_tiktok_token
        ],
        verbose=True,
        allow_delegation=False,
        llm=openai_llm,
        max_iter=3
    )
