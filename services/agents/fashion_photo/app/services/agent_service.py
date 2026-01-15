from crewai import Agent, Task, Crew, LLM
from app.services.image_generation import ImageGenerationTool
from app.core.config import settings
from langsmith import traceable

@traceable
def create_agent_and_crew(session: dict, assets: list, visual_context: str, history_text: str, message: str):
    """Create CrewAI agent and crew, then kickoff the task."""
    aiml_llm = LLM(
        model="openai/gpt-4o",
        base_url="https://api.aimlapi.com/v1",
        api_key=settings.AIML_API_KEY
    )
    
    visual_creator = Agent(
        role='Creative Director',
        goal='Guide the user through a fashion shoot workflow.',
        backstory=f"""You are an AI Creative Director.
        Current Stage: {session['stage']}
        
        Assets Available:
        - Avatars: {len(session['avatars'])}
        - Apparel: {len(session['apparel'])}
        - Generated Images: {len(session['generated'])}
        
        WORKFLOW:
        1. AVATAR_SELECTION: Ask user to select or upload an avatar.
        2. APPAREL_UPLOAD: Ask user to upload apparel.
        3. SCENE_SELECTION: Suggest 3 distinct, descriptive creative scenes upto 10 words based on vibe of apparel.
        4. GENERATION: Use 'image_generation_tool'. Use ALL Avatars and Apparel as input. 
           NOTE: The tool will automatically generate Front, Back, Side, and Motion shots for you.
           Just provide the SCENE description in the prompt.
        5. EDITING: If user wants changes, use the 'image_generation_tool' again and for reference take the images generated in the previous chat from URLs, don't make changes unless said. 
           CRITICAL: Verify you include the LAST generated image URL in the tool input for consistency if editing.
        """,
        tools=[ImageGenerationTool()],
        llm=aiml_llm
    )
    
    task_desc = f"""
    HISTORY:
    {history_text}
    
    CURRENT USER MESSAGE: {message}
    
    Current Stage: {session['stage']}
    Assets: {assets}
    {visual_context}
    
    INSTRUCTIONS:
    - If suggesting scenes, provide 3 DISTINCT, HIGHLY DETAILED, and VIVID scene descriptions. Paint a picture (lighting, mood, texture).
    - If the user selects an option (e.g., "Option 1" or "The second one"), refer to the HISTORY to find the matching scene description.
    - RESPOND NATURALLY but...
    - CRITICAL: You MUST include ALL image URLs returned by the 'image_generation_tool' in your final response. 
    - FORMATTING REQUIREMENT: At the end of your response, list the URLs as raw text, one per line, like this:
      GENERATED LINKS:
      https://...
      https://...
    - Do not use markdown resizing or hiding. Show the full links.
    """
    
    task = Task(
        description=task_desc,
        expected_output="Helpful response or generated image URLs.",
        agent=visual_creator
    )
    
    crew = Crew(agents=[visual_creator], tasks=[task])
    result = crew.kickoff()
    return result.raw

def process_chat_message(message: str, session: dict, assets: list, visual_context: str, history_text: str) -> str:
    """Process chat message using agent service."""
    return create_agent_and_crew(session, assets, visual_context, history_text, message)
