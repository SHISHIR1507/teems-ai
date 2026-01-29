"""
Calendar Sync Agent
Handles Google Calendar synchronization
"""
from crewai import Agent, LLM
from app.core.config import get_settings
from app.tools.calendar_tools import (
    sync_google_calendar,
    get_calendar_settings,
    update_timezone
)

settings = get_settings()

# Configure OpenAI LLM
openai_llm = LLM(
    model=settings.llm_model,
    base_url=settings.openai_base_url,
    api_key=settings.openai_api_key
)


def create_calendar_sync_agent() -> Agent:
    """Create the Calendar Sync Agent"""
    return Agent(
        role="Calendar Sync Specialist",
        goal="Sync Google Calendar events accurately and handle calendar-related requests",
        backstory="""You are an expert at Google Calendar integration and synchronization.
        You excel at:
        - Understanding calendar sync requests accurately
        - Using tools to get real calendar data (never make up events)
        - Handling sync errors and retries properly
        - Verifying sync status before reporting results
        - Being precise and accurate - no hallucinations
        
        You always use tools to get actual data from Google Calendar and the database.
        Never assume or make up calendar events, times, or settings.""",
        tools=[
            sync_google_calendar,
            get_calendar_settings,
            update_timezone
        ],
        verbose=True,
        allow_delegation=False,
        llm=openai_llm,
        max_iter=3
    )
