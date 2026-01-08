"""
Script Generator Agent - Generates UGC video scripts from images
"""
from crewai import Agent, LLM
from ugc_script_maker_tool import UGCScriptMakerTool
from dotenv import load_dotenv
import os
import langsmith
from langsmith import traceable

load_dotenv()

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
