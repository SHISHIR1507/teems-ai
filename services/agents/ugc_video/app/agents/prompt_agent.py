"""
Prompt Variator Agent - Generates 4 diverse UGC prompts
"""
from crewai import Agent, LLM
from app.tools.prompt_variator import PromptVariatorTool
from app.core.config import AIML_API_KEY
import langsmith
from langsmith import traceable


@traceable(
    name="create_prompt_agent",
    tags=["agent-creation", "prompt-generation"],
    metadata={"role": "prompt_variator", "num_tools": 1}
)
def create_prompt_agent():
    """
    Create an agent specialized in generating diverse prompts
    """
    with langsmith.trace(
        name="initialize_prompt_tool",
        tags=["tool-initialization"]
    ) as tool_trace:
        prompt_variator = PromptVariatorTool()
        tool_trace.outputs = {"tool": "PromptVariatorTool"}

    with langsmith.trace(
        name="configure_prompt_llm",
        tags=["llm-configuration", "gpt-5.2"]
    ) as llm_trace:
        llm = LLM(
            model="gpt-5.2-2025-12-11",
            api_key=AIML_API_KEY,
            base_url="https://api.aimlapi.com/v1",
            temperature=0.7
        )
        llm_trace.outputs = {"llm": "gpt-5.2-2025-12-11"}

    agent = Agent(
        role="UGC Prompt Variator",
        goal="Analyze person and product images, then call the prompt variator tool once to generate 4 prompts",
        backstory="""You are a creative prompt engineer specializing in UGC content with image analysis capabilities.

STRICT WORKFLOW:
1. Receive base_intent, person_image_url, and product_image_url from the task
2. Call the "UGC Prompt Variator" tool EXACTLY ONCE with all three parameters
3. When you see "[PROMPT_GENERATION_COMPLETE]" in the response, you are DONE
4. Return the 4 prompts exactly as received
5. DO NOT call the tool again
6. DO NOT modify or improve the prompts

COMPLETION SIGNAL: When you see "[PROMPT_GENERATION_COMPLETE]", immediately finish your task and return the prompts.""",
        tools=[prompt_variator],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=3  # think -> call tool -> return result
    )

    return agent
