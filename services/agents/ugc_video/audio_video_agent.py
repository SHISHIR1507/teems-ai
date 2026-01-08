"""
Audio+Video Generator Agent - Generates both audio and video from a script file
"""
from crewai import Agent, LLM
from ugc_audio_maker_tool import UGCAudioMakerTool
from ugc_vid_maker_tool import Veo3VideoMakerTool
from dotenv import load_dotenv
import os
import langsmith
from langsmith import traceable

load_dotenv()

@traceable(
    name="create_audio_video_agent",
    tags=["agent-creation", "audio-video-generation"],
    metadata={"role": "audio_video_generator", "num_tools": 2}
)
def create_audio_video_agent():
    """
    Create an agent that generates both audio and video from a script file
    """
    with langsmith.trace(
        name="initialize_audio_video_tools",
        tags=["tool-initialization"]
    ) as tool_trace:
        audio_tool = UGCAudioMakerTool()
        video_tool = Veo3VideoMakerTool()
        tool_trace.outputs = {"tools": ["UGCAudioMakerTool", "Veo3VideoMakerTool"]}

    with langsmith.trace(
        name="configure_audio_video_llm",
        tags=["llm-configuration", "gpt-5.2"]
    ) as llm_trace:
        llm = LLM(
            model="gpt-5.2-2025-12-11",
            api_key=os.getenv("AIML_API_KEY"),
            base_url="https://api.aimlapi.com/v1",
            temperature=0.7
        )
        llm_trace.outputs = {"llm": "gpt-5.2-2025-12-11"}

    agent = Agent(
        role="Audio and Video Generator",
        goal="Generate audio and video from provided dialogue and script, then immediately return the results",
        backstory="""You generate audio and video using two tools.

STRICT WORKFLOW:
1. Call UGC Audio Generator tool with the dialogue text
2. Wait for audio filename (e.g., audio_xxxxx.mp3)
3. Call Veo3.1 Image-to-Video Generator tool with the video script
4. Wait for video URL (starts with https://)
5. IMMEDIATELY return in this EXACT format:

Audio filename: <audio_filename>
Video URL: <video_url>

CRITICAL RULES:
- Call each tool EXACTLY ONCE
- Do NOT call tools multiple times
- Do NOT add extra commentary after returning the results
- When you see both the audio filename AND video URL, format your response and STOP
- Your response must contain "Audio filename:" and "Video URL:" on separate lines""",
        tools=[audio_tool, video_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=5  # think -> call audio -> call video -> format response -> done
    )

    return agent
