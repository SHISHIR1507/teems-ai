"""
Chat Agent (Kai) - Conversational UGC creator and creative director
"""
from crewai import Agent, LLM
from app.core.config import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL, LANGCHAIN_PROJECT
import os
import langsmith
from langsmith import traceable

# Initialize LangSmith tracing
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = LANGCHAIN_PROJECT


@traceable(
    name="create_chat_agent",
    tags=["agent-creation", "crewai", "chat"],
    metadata={"model": LLM_MODEL, "provider": "openai", "mode": "chat"}
)
def create_chat_agent():
    """
    Create Kai - a conversational UGC creator and creative director
    """
    # Log which API is being used
    provider = "OpenAI" if "openai.com" in OPENAI_BASE_URL else "AIML" if "aimlapi" in OPENAI_BASE_URL else "Unknown"
    print(f"🤖 Chat using: {provider} | URL: {OPENAI_BASE_URL} | Key: {OPENAI_API_KEY[:12]}...")
    
    with langsmith.trace(
        name="configure_chat_llm",
        tags=["llm-configuration", "openai", "chat"]
    ) as llm_trace:
        llm = LLM(
            model=LLM_MODEL,
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            temperature=0.7
        )
        llm_trace.outputs = {"llm": LLM_MODEL}

    agent = Agent(
        role="Kai - Senior UGC Creator",
        goal="Guide brands through UGC creation with confidence and creative direction",
        backstory="""You are Kai — a senior UGC creator and creative director.

You do not sound like software. You do not ask form-like questions. You reflect understanding first, then guide.

You speak like a real teammate running UGC for the brand. You're confident, calm, human, and creator-led.

Your capabilities:
- Understand brand context (industry, audience, vibe)
- Generate 4 diverse UGC images when users upload a person image and a product image
- Create variations with different poses, angles, and styles
- Provide creative direction on tone, visuals, and hooks

You never mention tools, agents, models, or internal processes.

When talking to users:
- Use short paragraphs
- No bullet dumping
- No hype language
- Show you understand their space
- Be decisive and clear

If users haven't uploaded images yet, guide them naturally to do so.""",
        tools=[],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=3
    )

    return agent
