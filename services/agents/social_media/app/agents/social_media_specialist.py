"""
Social Media Specialist Agent
Main agent that understands requirements and coordinates tasks
"""
from crewai import Agent, LLM
from app.core.config import get_settings
from app.tools.tiktok_tools import post_to_tiktok, get_tiktok_posts, refresh_tiktok_token
from app.tools.facebook_tools import post_to_facebook, get_facebook_posts
from app.tools.platform_tools import get_user_posts, get_connected_platforms

settings = get_settings()

# Configure AIML LLM
aiml_llm = LLM(
    model=settings.llm_model,
    base_url=settings.aiml_base_url,
    api_key=settings.aiml_api_key
)


def create_social_media_specialist_agent() -> Agent:
    """Create the Social Media Specialist agent"""
    return Agent(
        role="Social Media Specialist",
        goal="Help users post videos to multiple social media platforms (TikTok, Facebook) by understanding their requirements accurately and asking clarifying questions when needed",
        backstory="""You are an expert social media manager with deep knowledge of multiple platforms including TikTok and Facebook.
        You excel at:
        - Understanding user requirements accurately
        - Asking clarifying questions when information is missing (which platform, video URL, caption, hashtags)
        - Providing helpful suggestions based on available options
        - Never making assumptions - always use tools to get accurate information
        - Being friendly, professional, and patient
        - Handling multi-platform posting requests
        
        You have access to all social media tools and can coordinate with specialized agents when needed.
        Always confirm actions before executing them and provide clear status updates.
        
        When a user wants to post:
        1. Extract video URL, caption, hashtags, and target platform(s)
        2. If platform not specified, ask which platform(s) they want to use
        3. Check if the platform is connected using get_connected_platforms
        4. Use the appropriate posting tool
        5. Confirm success with details
        
        Supported platforms:
        - TikTok (fully working)
        - Facebook (fully working)""",
        tools=[
            post_to_tiktok,
            get_tiktok_posts,
            refresh_tiktok_token,
            post_to_facebook,
            get_facebook_posts,
            get_user_posts,
            get_connected_platforms
        ],
        verbose=True,
        allow_delegation=True,
        llm=aiml_llm,
        max_iter=5
    )
