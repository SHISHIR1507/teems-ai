"""
Meeting Join Agent
Executes meeting join operations via Nylas API
"""
from crewai import Agent, LLM
from app.core.config import get_settings
from app.tools.meeting_tools import (
    join_meeting_via_nylas,
    check_meeting_status,
    get_notetaker_status
)

settings = get_settings()

# Configure AIML LLM
aiml_llm = LLM(
    model=settings.llm_model,
    base_url=settings.aiml_base_url,
    api_key=settings.aiml_api_key
)


def create_meeting_join_agent() -> Agent:
    """Create the Meeting Join Agent"""
    return Agent(
        role="Meeting Join Specialist",
        goal="Join meetings via Nylas API accurately and report actual join status",
        backstory="""You are an expert at joining meetings through the Nylas API.
        You excel at:
        - Executing join operations via Nylas API using tools
        - Verifying join status using actual API responses
        - Reporting accurate join results (never make up status)
        - Handling join errors properly
        - Being precise - only report what actually happened
        
        You always use tools to join meetings and check status.
        Never report join success without verifying with the API.
        Never hallucinate join status or notetaker IDs.""",
        tools=[
            join_meeting_via_nylas,
            check_meeting_status,
            get_notetaker_status
        ],
        verbose=True,
        allow_delegation=False,
        llm=aiml_llm,
        max_iter=3
    )
