"""
Meeting Detection Agent
Identifies meetings to join from calendar events
"""
from crewai import Agent, LLM
from app.core.config import get_settings
from app.tools.calendar_tools import get_upcoming_meetings
from app.tools.meeting_tools import detect_meeting_platform
from app.tools.timezone_tools import get_user_timezone, calculate_join_time

settings = get_settings()

# Configure OpenAI LLM
openai_llm = LLM(
    model=settings.llm_model,
    base_url=settings.openai_base_url,
    api_key=settings.openai_api_key
)


def create_meeting_detection_agent() -> Agent:
    """Create the Meeting Detection Agent"""
    return Agent(
        role="Meeting Detection Specialist",
        goal="Identify meetings that need to be joined and validate meeting information",
        backstory="""You are an expert at analyzing calendar events and identifying joinable meetings.
        You excel at:
        - Analyzing calendar events to find meetings with valid links
        - Detecting meeting platforms accurately using tools
        - Validating meeting links before attempting to join
        - Calculating exact join times based on event start times
        - Never making assumptions - always use tools to verify
        
        You always use tools to get real calendar data and detect platforms.
        Never guess meeting platforms or make up meeting information.""",
        tools=[
            get_upcoming_meetings,
            detect_meeting_platform,
            get_user_timezone,
            calculate_join_time
        ],
        verbose=True,
        allow_delegation=False,
        llm=openai_llm,
        max_iter=3
    )
