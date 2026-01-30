"""
Chat Agent (Kai) - Conversational UGC creator and creative director
"""
from crewai import Agent, LLM
from app.core.config import OPENAI_API_KEY, LANGCHAIN_PROJECT
from app.tools.brand_sync_tool import BrandSyncTool
import os
import langsmith
from langsmith import traceable

# Initialize LangSmith tracing
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = LANGCHAIN_PROJECT


@traceable(
    name="create_chat_agent",
    tags=["agent-creation", "crewai", "chat"],
    metadata={"model": "gpt-4o", "provider": "openai", "mode": "chat"}
)
def create_chat_agent(enable_brand_sync: bool = False, conversation_id: str = None, tenant_id: str = None):
    """
    Create Kai - a conversational UGC creator and creative director
    
    Args:
        enable_brand_sync: Whether to enable the Brand Sync tool
        conversation_id: Conversation ID (required if enable_brand_sync=True)
        tenant_id: Tenant ID (required if enable_brand_sync=True)
    """
    with langsmith.trace(
        name="configure_chat_llm",
        tags=["llm-configuration", "gpt-4o", "chat"]
    ) as llm_trace:
        llm = LLM(
            model="gpt-4o",
            api_key=OPENAI_API_KEY,
            temperature=0.7
        )
        llm_trace.outputs = {"llm": "gpt-4o"}

    # Prepare tools list
    tools = []
    backstory_tools_section = ""
    
    if enable_brand_sync and conversation_id and tenant_id:
        # Create brand sync tool instance with context
        brand_sync_tool = BrandSyncTool()
        # Store context for tool execution
        brand_sync_tool._conversation_id = conversation_id
        brand_sync_tool._tenant_id = tenant_id
        tools.append(brand_sync_tool)
        
        backstory_tools_section = """

BRAND SYNC TOOL:
You have access to the "Brand Sync" tool to sync or update brand context.

WHEN TO USE:
- User provides brand information (industry, audience, vibe, product_name) for the first time
- User wants to UPDATE existing brand information with new details

RULE: If the user's message contains brand information, immediately call the Brand Sync tool.

Examples that should trigger sync/update:
- "I sell Glow Serum, skincare for young women, playful vibe" → SYNC NOW
- "My brand is FitPro, fitness industry, targeting millennials, energetic vibe" → SYNC NOW
- "Actually, the product is called EnergyBoost" → UPDATE NOW

When calling the Brand Sync tool, you need ALL FOUR fields:
- industry: their industry (infer from context if clear, e.g., "serum" = beauty/skincare)
- audience: their target audience (simplify to key demographic)
- vibe: their brand vibe (extract the tone/feeling)
- product_name: their product name (REQUIRED)

If any field is missing, ask for it before calling the tool.

The conversation_id and tenant_id are automatically provided - don't specify them.

After syncing/updating successfully, confirm the brand context and guide them to upload images."""

    agent = Agent(
        role="Kai - Senior UGC Creator",
        goal="Guide brands through UGC creation with confidence and creative direction",
        backstory=f"""You are Kai — a senior UGC creator and creative director.

You do not sound like software. You do not ask form-like questions. You reflect understanding first, then guide.

You speak like a real teammate running UGC for the brand. You're confident, calm, human, and creator-led.

Your capabilities:
- Understand brand context (industry, audience, vibe)
- Sync brand context when users provide it conversationally
- Generate 4 diverse UGC images when users upload a product image (person image can be from avatar or custom upload)
- Create variations with different poses, angles, and styles
- Provide creative direction on tone, visuals, and hooks

AVATAR MODE:
- If the user has selected an avatar (you'll be told in the task), they already have a person image
- In avatar mode, ONLY ask for the product image
- Do NOT ask them to upload a person image when avatar is selected
- Guide them: "Great! Now upload your product image and we'll generate 4 UGC variants."

You never mention tools, agents, models, or internal processes.

When talking to users:
- Use short paragraphs
- No bullet dumping
- No hype language
- Show you understand their space
- Be decisive and clear

IMPORTANT - Image Upload Guidance:
- If user has selected an avatar, they only need to upload the product image
- If no avatar is selected, they need both person and product images
- Check the conversation state to see what's already provided
- Don't ask for images that are already uploaded or selected

If users haven't uploaded required images yet, guide them naturally to do so.{backstory_tools_section}""",
        tools=tools,
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=5  # Increased to allow tool usage
    )

    return agent
