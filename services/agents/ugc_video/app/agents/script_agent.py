"""
Script Generator Agent - Generates UGC video scripts from images
"""
from crewai import Agent, LLM
from app.tools.script_maker import UGCScriptMakerTool
from app.core.config import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL
import langsmith
from langsmith import traceable


@traceable(
    name="create_script_agent",
    tags=["agent-creation", "script-generation"],
    metadata={"role": "script_generator", "num_tools": 1}
)
def create_script_agent():
    """
    Create an agent specialized in generating UGC video scripts
    """
    with langsmith.trace(
        name="initialize_script_tool",
        tags=["tool-initialization"]
    ) as tool_trace:
        script_tool = UGCScriptMakerTool()
        tool_trace.outputs = {"tool": "UGCScriptMakerTool"}

    with langsmith.trace(
        name="configure_script_llm",
        tags=["llm-configuration", "openai"]
    ) as llm_trace:
        llm = LLM(
            model=LLM_MODEL,
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            temperature=0.7
        )
        llm_trace.outputs = {"llm": LLM_MODEL}

    agent = Agent(
        role="UGC Video Script Creator",
        goal="Call the UGC Script Maker tool with the provided parameters",
        backstory="""You are a tool executor. Your ONLY job is to call the UGC Script Maker tool.

STRICT INSTRUCTIONS:
1. Read the parameters from your task
2. Call the "UGC Script Maker" tool with those exact parameters
3. Return what the tool gives you

YOU CANNOT:
- Skip calling the tool
- Return the filename without calling the tool
- Think about what the output should be
- Generate your own response

YOU MUST:
- Always call the tool first
- Use all parameters given in the task
- Wait for the tool's response before answering""",
        tools=[script_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=2,  # Reduced to force tool call
        max_rpm=None,
        force_tool_use=True  # Force tool usage
    )

    return agent
