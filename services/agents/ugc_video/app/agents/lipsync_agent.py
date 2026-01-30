"""
Lipsync Agent - Combines video and audio to create lipsynced UGC videos
"""
from crewai import Agent, LLM
from app.tools.lipsync import LipsyncTool
from app.core.config import OPENAI_API_KEY
import langsmith
from langsmith import traceable


@traceable(
    name="create_lipsync_agent",
    tags=["agent-creation", "lipsync"],
    metadata={"role": "lipsync_generator", "num_tools": 1}
)
def create_lipsync_agent():
    """
    Create an agent specialized in lipsyncing videos with audio using Sync API
    """
    with langsmith.trace(
        name="initialize_lipsync_tool",
        tags=["tool-initialization"]
    ) as tool_trace:
        lipsync_tool = LipsyncTool()
        tool_trace.outputs = {"tool": "LipsyncTool"}

    with langsmith.trace(
        name="configure_lipsync_llm",
        tags=["llm-configuration", "gpt-4o"]
    ) as llm_trace:
        llm = LLM(
            model="gpt-4o",
            api_key=OPENAI_API_KEY,
            temperature=0.7
        )
        llm_trace.outputs = {"llm": "gpt-4o"}

    agent = Agent(
        role="UGC Lipsync Specialist",
        goal="Call Lipsync Video Generator tool once",
        backstory="""You call the Lipsync Video Generator tool.

INSTRUCTIONS:
1. Call the tool with: video_url, audio_url, output_filename
2. Wait for response (this takes time)
3. Return the lipsynced video URL

DO NOT call the tool twice.
When you see "Success! Output URL:" you are done.""",
        tools=[lipsync_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=2
    )

    return agent
