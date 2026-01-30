"""
Image Generator Agent - Generates 4 UGC images from prompts
"""
from crewai import Agent, LLM
from app.tools.banana_ugc import BananaUGCTool
from app.core.config import OPENAI_API_KEY
import langsmith
from langsmith import traceable


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
        tags=["llm-configuration", "gpt-4o"]
    ) as llm_trace:
        llm = LLM(
            model="gpt-4o",
            api_key=OPENAI_API_KEY,
            temperature=0.7
        )
        llm_trace.outputs = {"llm": "gpt-4o"}

    agent = Agent(
        role="UGC Image Generator",
        goal="Call the Banana tool once with 4 prompts, then immediately return the tool output",
        backstory="""You are an expert at generating UGC images using the Banana UGC tool.

WORKFLOW:
1. Extract the 4 prompts from the previous task
2. Call "Banana UGC Image Generator" tool ONCE with all parameters
3. When you see the tool output (starts with ✅ SUCCESS or ⚠️ PARTIAL SUCCESS), your task is COMPLETE
4. Return the tool output EXACTLY as received - do not modify it

COMPLETION SIGNALS - When you see ANY of these, you are DONE:
- "✅ SUCCESS: All 4 images generated"
- "[S3_URLS]" markers in the response
- "⚠️ PARTIAL SUCCESS"

DO NOT:
- Call the tool multiple times
- Reformat or summarize the output
- Think about what to do after seeing the tool output
- Try to improve or validate the result

Your final answer = the tool's exact output.""",
        tools=[banana_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=5  # Allow: think -> call tool -> see result -> return
    )

    return agent
