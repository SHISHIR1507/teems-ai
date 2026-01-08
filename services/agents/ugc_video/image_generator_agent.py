"""
Image Generator Agent - Generates 4 UGC images from prompts
"""
from crewai import Agent, LLM
from banana_tool_with_langsmith import BananaUGCTool
from dotenv import load_dotenv
import os
import langsmith
from langsmith import traceable

load_dotenv()

@traceable(
    name="create_image_generator_agent",
    tags=["agent-creation", "image-generation"],
    metadata={"role": "image_generator", "num_tools": 1}
)
def create_image_generator_agent():
    """
    Create an agent specialized in generating UGC images
    """
    with langsmith.trace(
        name="initialize_banana_tool",
        tags=["tool-initialization"]
    ) as tool_trace:
        banana_tool = BananaUGCTool()
        tool_trace.outputs = {"tool": "BananaUGCTool"}

    with langsmith.trace(
        name="configure_image_llm",
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
        role="UGC Image Generator",
        goal="Generate exactly 4 UGC images by calling the Banana tool ONCE with all 4 prompts and return the tool's output",
        backstory="""You are an expert at generating UGC images using the Banana UGC tool.

MANDATORY WORKFLOW - Follow this EXACT sequence:

STEP 1: Extract the 4 prompts from the previous task
STEP 2: Call the Banana UGC Image Generator tool EXACTLY ONCE
   - Pass all 4 prompts as a list: prompts=["prompt1", "prompt2", "prompt3", "prompt4"]
   - The tool will generate all 4 images in parallel
STEP 3: Return the EXACT tool output (including [S3_URLS] markers)

CRITICAL RULES:
- Make EXACTLY 1 tool call (with all 4 prompts)
- DO NOT loop or call the tool multiple times
- The tool handles parallel generation automatically
- After the tool completes, return its EXACT output without modification
- The tool output contains [S3_URLS] markers - preserve them exactly
- DO NOT try to reformat or summarize the tool output
- Your final answer should be the tool's complete response

This is a single-call operation. The tool does the parallelization internally.""",
        tools=[banana_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=3  # think -> call tool once -> return result
    )

    return agent
