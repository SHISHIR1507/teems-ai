"""
CrewAI Agent Factories
Creates specialized agents for UGC video generation workflows
"""
from crewai import Agent, LLM
import langsmith
from langsmith import traceable

from ..config import get_settings
from ..tools import (
    BananaUGCTool,
    PromptVariatorTool,
    UGCScriptMakerTool,
    Veo3VideoMakerTool,
)


@traceable(
    name="create_chat_agent",
    tags=["agent-creation", "crewai", "chat"],
    metadata={"model": "gpt-5-2025-08-07", "provider": "aiml-api", "mode": "chat"}
)
def create_chat_agent():
    """
    Create a conversational agent for general chat without tools
    """
    settings = get_settings()
    
    with langsmith.trace(
        name="configure_chat_llm",
        tags=["llm-configuration", "gpt-5", "chat"]
    ) as llm_trace:
        llm = LLM(
            model="openai/gpt-5-2025-08-07",
            api_key=settings.aiml_api_key,
            base_url=settings.aiml_base_url,
            temperature=0.7
        )
        llm_trace.outputs = {"llm": "openai/gpt-5-2025-08-07"}

    agent = Agent(
        role="UGC AI Assistant",
        goal="Help users understand UGC generation capabilities and answer their questions",
        backstory="""You are a friendly AI assistant specializing in User-Generated Content (UGC) video creation.

Your capabilities:
- Generate 4 diverse UGC images when users upload a person image and a product image (or screenshot/logo)
- Support three types: Physical Products, Digital Products (apps/websites), and Services
- Use advanced AI models (nano-banana-pro-edit) for realistic image composition
- Create variations with different poses, angles, and styles
- Generate video scripts and videos from selected images
- Provide guidance on how to use the UGC generation system

When users ask what you can do, explain:
1. You can generate authentic-looking UGC images by combining a person photo with a product photo, screenshot, or logo
2. You support three types: Physical Products, Digital Products, and Services
3. You create 4 different image variants for variety
4. You can generate video scripts and videos from the generated images
5. Users need to upload appropriate images based on the type they want

Be helpful, friendly, and informative. If users haven't uploaded images yet, encourage them to do so to try the UGC generation.""",
        tools=[],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=3
    )

    return agent


@traceable(
    name="create_prompt_agent",
    tags=["agent-creation", "prompt-generation"],
    metadata={"role": "prompt_variator", "num_tools": 1}
)
def create_prompt_agent():
    """
    Create an agent specialized in generating diverse prompts
    """
    settings = get_settings()
    
    with langsmith.trace(
        name="initialize_prompt_tool",
        tags=["tool-initialization"]
    ) as tool_trace:
        prompt_variator = PromptVariatorTool()
        tool_trace.outputs = {"tool": "PromptVariatorTool"}

    with langsmith.trace(
        name="configure_prompt_llm",
        tags=["llm-configuration", "gpt-5"]
    ) as llm_trace:
        llm = LLM(
            model="openai/gpt-5-2025-08-07",
            api_key=settings.aiml_api_key,
            base_url=settings.aiml_base_url,
            temperature=0.7
        )
        llm_trace.outputs = {"llm": "openai/gpt-5-2025-08-07"}

    agent = Agent(
        role="UGC Prompt Variator",
        goal="Call the prompt variator tool once and return the 4 prompts",
        backstory="""You are a creative prompt engineer specializing in UGC content.

STRICT WORKFLOW:
1. Call the "UGC Prompt Variator" tool EXACTLY ONCE with the base intent
2. When you see "[PROMPT_GENERATION_COMPLETE]" in the response, you are DONE
3. Return the 4 prompts exactly as received
4. DO NOT call the tool again
5. DO NOT modify or improve the prompts

COMPLETION SIGNAL: When you see "[PROMPT_GENERATION_COMPLETE]", immediately finish your task and return the prompts.""",
        tools=[prompt_variator],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=3  # think -> call tool -> return result
    )

    return agent


@traceable(
    name="create_image_generator_agent",
    tags=["agent-creation", "image-generation"],
    metadata={"role": "image_generator", "num_tools": 1}
)
def create_image_generator_agent(ugc_type: str = "physical_product"):
    """
    Create an agent specialized in generating UGC images
    Supports all three UGC types: physical_product, digital_product, service
    """
    settings = get_settings()
    
    with langsmith.trace(
        name="initialize_banana_tool",
        tags=["tool-initialization"]
    ) as tool_trace:
        banana_tool = BananaUGCTool()
        tool_trace.outputs = {"tool": "BananaUGCTool"}

    with langsmith.trace(
        name="configure_image_llm",
        tags=["llm-configuration", "gpt-5"]
    ) as llm_trace:
        llm = LLM(
            model="openai/gpt-5-2025-08-07",
            api_key=settings.aiml_api_key,
            base_url=settings.aiml_base_url,
            temperature=0.7
        )
        llm_trace.outputs = {"llm": "openai/gpt-5-2025-08-07"}

    type_specific_instructions = ""
    if ugc_type == "digital_product":
        type_specific_instructions = """
For digital products:
- Use screenshot_path parameter when calling the tool
- The tool will combine person image with screenshot to show device with digital product
"""
    elif ugc_type == "service":
        type_specific_instructions = """
For services:
- Use logo_path parameter when calling the tool (if available)
- The tool will create a scene where person talks about the service
- Logo can be naturally integrated into the scene
"""

    agent = Agent(
        role="UGC Image Generator",
        goal="Generate exactly 4 UGC images by calling the tool 4 times with different filenames",
        backstory=f"""You are an expert at generating UGC images using the Banana UGC tool.
{type_specific_instructions}

MANDATORY WORKFLOW - Follow this EXACT sequence:

STEP 1: Extract the 4 prompts from the previous task
STEP 2: Call tool with Prompt 1 → output_filename="generated_ugc_image_1.png"
STEP 3: Call tool with Prompt 2 → output_filename="generated_ugc_image_2.png"
STEP 4: Call tool with Prompt 3 → output_filename="generated_ugc_image_3.png"
STEP 5: Call tool with Prompt 4 → output_filename="generated_ugc_image_4.png"
STEP 6: Report completion

CRITICAL RULES:
- Make EXACTLY 4 tool calls (one per prompt)
- Each call MUST use a DIFFERENT output_filename
- Filenames: generated_ugc_image_1.png, generated_ugc_image_2.png, generated_ugc_image_3.png, generated_ugc_image_4.png
- Always pass ugc_type="{ugc_type}" to the tool
- After seeing "✅ SUCCESS" 4 times, you are DONE
- Track your progress: "Completed 1/4", "Completed 2/4", "Completed 3/4", "Completed 4/4"

When you see "✅ SUCCESS" for the 4th time, immediately finish and report all 4 filenames.""",
        tools=[banana_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=15  # 4 tool calls + thinking + reporting
    )

    return agent


@traceable(
    name="create_script_agent",
    tags=["agent-creation", "script-generation"],
    metadata={"role": "script_generator", "num_tools": 1}
)
def create_script_agent(ugc_type: str = "physical_product"):
    """
    Create an agent specialized in generating UGC video scripts
    """
    settings = get_settings()
    
    with langsmith.trace(
        name="initialize_script_tool",
        tags=["tool-initialization"]
    ) as tool_trace:
        script_tool = UGCScriptMakerTool()
        tool_trace.outputs = {"tool": "UGCScriptMakerTool"}

    with langsmith.trace(
        name="configure_script_llm",
        tags=["llm-configuration", "gpt-5"]
    ) as llm_trace:
        llm = LLM(
            model="openai/gpt-5-2025-08-07",
            api_key=settings.aiml_api_key,
            base_url=settings.aiml_base_url,
            temperature=0.7
        )
        llm_trace.outputs = {"llm": "openai/gpt-5-2025-08-07"}

    agent = Agent(
        role="UGC Video Script Creator",
        goal="Generate professional 8-second UGC video scripts optimized for Veo 3",
        backstory=f"""You are an expert UGC video script writer specializing in authentic creator content.

STRICT WORKFLOW:
1. Receive a UGC image reference and product/service details
2. Call the "UGC Script Maker" tool EXACTLY ONCE
3. Always pass ugc_type="{ugc_type}" to the tool
4. When you see the complete script output, you are DONE
5. Return the script exactly as received

CRITICAL RULES:
- Call the tool ONLY ONCE
- Do NOT modify or improve the script
- Do NOT call the tool again
- After receiving the script, your task is complete

The script will be optimized for Veo 3 video generation with authentic UGC style.""",
        tools=[script_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=3  # think -> call tool -> return result
    )

    return agent


@traceable(
    name="create_video_agent",
    tags=["agent-creation", "video-generation"],
    metadata={"role": "video_generator", "num_tools": 1}
)
def create_video_agent():
    """
    Create an agent specialized in generating UGC videos using Veo-3.1
    """
    settings = get_settings()
    
    with langsmith.trace(
        name="initialize_video_tool",
        tags=["tool-initialization"]
    ) as tool_trace:
        video_tool = Veo3VideoMakerTool()
        tool_trace.outputs = {"tool": "Veo3VideoMakerTool"}

    with langsmith.trace(
        name="configure_video_llm",
        tags=["llm-configuration", "gpt-5"]
    ) as llm_trace:
        llm = LLM(
            model="openai/gpt-5-2025-08-07",
            api_key=settings.aiml_api_key,
            base_url=settings.aiml_base_url,
            temperature=0.7
        )
        llm_trace.outputs = {"llm": "openai/gpt-5-2025-08-07"}

    agent = Agent(
        role="UGC Video Generator",
        goal="Call the video generation tool once and return the video URL",
        backstory="""You are an expert at generating UGC videos using Google's Veo-3.1 model.

STRICT WORKFLOW:
1. Extract the script text from the previous agent's output
2. Call the "Veo3.1 Image-to-Video Generator" tool EXACTLY ONCE
3. When you see "[VIDEO_GENERATION_COMPLETE]", you are DONE
4. Return the video URL and finish immediately

CRITICAL RULES:
- Call the tool ONLY ONCE - never call it again
- When you see "[VIDEO_GENERATION_COMPLETE]", your task is finished
- Do NOT try to verify, check, or regenerate the video
- Do NOT call the tool multiple times
- Simply return the video URL and stop

COMPLETION SIGNAL: "[VIDEO_GENERATION_COMPLETE]" means your job is done.""",
        tools=[video_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=4  # call tool -> get result -> return -> done
    )

    return agent

