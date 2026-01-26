"""
Concierge agent for the posting flow. No post tools — orchestrator posts after confirmation.
"""
from crewai import Agent, LLM
from app.core.config import get_settings
from app.tools.flow_tools import (
    register_content_link,
    get_conversation_assets,
    suggest_caption_hashtags,
)
from app.tools.platform_tools import get_connected_platforms, get_user_posts

settings = get_settings()
aiml_llm = LLM(
    model=settings.llm_model,
    base_url=settings.aiml_base_url,
    api_key=settings.aiml_api_key,
)


def create_concierge_agent(tools: list) -> Agent:
    """Create Concierge agent with given tools (no post tools)."""
    return Agent(
        role="Social Media Concierge",
        goal="Guide users naturally through the posting flow: get content, suggest caption and hashtags, \
incorporate feedback, and seek confirmation before posting. Never post yourself; the system posts after confirmation.",
        backstory="""You are a friendly social media assistant. You help users post content to TikTok.
You never invent platform features or capabilities. You use tools for facts.
Flow: (1) Get content — ask user to upload or share a link (image or video). (2) Suggest caption and hashtags \
using suggest_caption_hashtags. (3) Ask for feedback and revise if needed. (4) When they're happy, \
clearly ask if you should post to their TikTok (use get_connected_platforms to confirm they're connected). \
(5) Wait for confirmation. Do not post — the system posts once they confirm.
If they deflect or don't confirm, continue the conversation naturally and ask again when appropriate.
If they ask for history or connected platforms, use get_user_posts or get_connected_platforms."""
        ,
        tools=tools,
        verbose=True,
        allow_delegation=False,
        llm=aiml_llm,
        max_iter=6,
    )
