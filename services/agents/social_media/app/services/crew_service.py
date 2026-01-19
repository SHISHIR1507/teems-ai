"""
CrewAI Service - Social Media Agent
Orchestrates multi-platform posting using CrewAI agents and tools
"""

import os
from crewai import Agent, Task, Crew, LLM
from app.tools.social_media_tools import post_to_tiktok, post_to_facebook, get_user_posts
from app.core.config import get_settings
import concurrent.futures

settings = get_settings()

# Configure AIML LLM using CrewAI's LLM class (clean approach!)
aiml_llm = LLM(
    model="openai/gpt-4o",
    base_url=settings.aiml_base_url,
    api_key=settings.aiml_api_key
)

# Thread pool for running CrewAI without blocking
executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)


class SocialMediaCrew:
    """CrewAI-based social media posting service"""
    
    def __init__(self):
        """Initialize the social media agent"""
        self.agent = Agent(
            role="Social Media Manager",
            goal="Help users post videos to TikTok and other social media platforms",
            backstory="""You are an expert social media manager who helps users post 
            content to various platforms. You understand video URLs, captions, and hashtags.
            
            You can currently post to:
            - TikTok (fully working)
            - Facebook (coming soon)
            
            When users ask to post, extract the video URL, caption, and hashtags,
            then ask which platform they want to use if not specified.
            
            Always be friendly, helpful, and confirm actions before executing them.""",
            tools=[post_to_tiktok, post_to_facebook, get_user_posts],
            verbose=True,
            allow_delegation=False,
            llm=aiml_llm  # Use CrewAI's LLM with AIML API!
        )
    
    def process_message(self, user_id: int, message: str) -> str:
        """
        Process a user message using CrewAI agent
        
        Args:
            user_id: User ID
            message: User's message
        
        Returns:
            Agent's response
        """
        
        # Create task with user context
        task = Task(
            description=f"""
            User ID: {user_id}
            User Message: {message}
            
            Process the user's request. If they want to post a video:
            1. Extract video URL, caption, and hashtags from their message
            2. Ask which platform if not specified (TikTok/Facebook)
            3. Use the appropriate tool to post
            4. Confirm success with details
            
            If they ask about their posts, use the get_user_posts tool.
            
            Be conversational and helpful!
            """,
            agent=self.agent,
            expected_output="A friendly response to the user's request"
        )
        
        # Create and run crew
        crew = Crew(
            agents=[self.agent],
            tasks=[task],
            verbose=False
        )
        
        try:
            # Run crew.kickoff() in thread pool to avoid blocking
            # This allows tools to call the API endpoints
            future = executor.submit(crew.kickoff)
            result = future.result(timeout=120)  # 2 minute timeout
            return str(result)
        except concurrent.futures.TimeoutError:
            return "Sorry, the request took too long to process. Please try again."
        except Exception as e:
            return f"Sorry, I encountered an error: {str(e)}"


# Singleton instance
_crew_instance = None

def get_crew_service() -> SocialMediaCrew:
    """Get or create CrewAI service instance"""
    global _crew_instance
    if _crew_instance is None:
        _crew_instance = SocialMediaCrew()
    return _crew_instance
