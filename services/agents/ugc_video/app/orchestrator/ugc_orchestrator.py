"""
UGC Orchestrator with 2-Agent Sequential Workflow
Agent 1: Prompt Variator → Agent 2: Image Generator
"""
from crewai import Task, Crew
from app.agents.prompt_agent import create_prompt_agent
from app.agents.image_agent import create_image_generator_agent
from app.agents.chat_agent import create_chat_agent
from app.core.config import LANGCHAIN_PROJECT
import os
import langsmith
from langsmith import traceable

# Initialize LangSmith tracing
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = LANGCHAIN_PROJECT


@traceable(
    name="handle_brand_sync",
    tags=["brand-sync", "orchestrator"],
    metadata={"mode": "brand-reflection"}
)
def handle_brand_sync(industry: str, audience: str, vibe: str):
    """
    Handle brand sync - Kai reflects brand understanding back to user
    Direct LLM call, no sub-agents, returns natural language
    """
    agent = create_chat_agent()
    
    task = Task(
        description=f"""You are Kai, a senior UGC creator.

You've received brand signals:

Industry: {industry}
Audience: {audience}
Vibe: {vibe}

Your task:
- Reflect the brand back confidently
- Rephrase insights in your own words
- Show you understand the space
- Set creative direction (tone, visuals, hooks)
- Do NOT repeat inputs verbatim
- Do NOT ask questions yet
- End by inviting light correction

Tone: Confident, calm, human, creator-led. Short paragraphs. No bullet dumping. No hype language.

Example style:
"Alright — here's how I'm reading your brand right now.

You're in [industry insight]. Your audience is [audience understanding]. The vibe you're going for is [vibe interpretation].

For UGC, that means [creative direction]. We'll focus on [specific approach].

If anything feels off, tell me and I'll adapt."

Now respond based on the brand signals above.""",
        expected_output="Natural, confident brand reflection in Kai's voice",
        agent=agent,
        human_input=False
    )
    
    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=True,
        max_iter=3,
        full_output=False
    )
    
    result = crew.kickoff()
    return result


@traceable(
    name="chat_with_agent",
    tags=["chat", "conversation"],
    metadata={"mode": "general-chat"}
)
def chat_with_agent(message: str, brand_context: dict = None):
    """
    Handle general chat without image generation
    Can use brand context if available
    """
    agent = create_chat_agent()
    
    context_note = ""
    if brand_context and brand_context.get('locked'):
        context_note = f"""
        
Brand context (already locked):
- Industry: {brand_context.get('industry')}
- Audience: {brand_context.get('audience')}
- Vibe: {brand_context.get('vibe')}

Reference this naturally if relevant to the conversation."""
    
    task = Task(
        description=f"""Respond to the user's message: "{message}"
        
Be helpful and speak like Kai - confident, calm, creator-led.{context_note}""",
        expected_output="A helpful response in Kai's voice",
        agent=agent,
        human_input=False
    )
    
    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=True,
        max_iter=3,
        full_output=False
    )
    
    result = crew.kickoff()
    return result


@traceable(
    name="generate_ugc_with_orchestrator",
    tags=["multi-agent-orchestration", "ugc", "end-to-end"],
    metadata={"workflow": "2-agent-sequential", "expected_images": 4}
)
def generate_ugc_with_orchestrator(
    person_image_url: str,
    product_image_url: str,
    base_intent: str,
    industry: str,
    audience: str,
    vibe: str,
    conversation_id: str = None,
    upload_to_s3: bool = False
):
    """
    Generate 4 diverse UGC images using 2-agent sequential workflow.
    
    Workflow:
    1. Agent 1 (Prompt Variator) generates 4 prompts
    2. Agent 2 (Image Generator) generates 4 images
    
    Args:
        person_image_url: S3 URL to the person image
        product_image_url: S3 URL to the product image
        base_intent: Base intent for image generation
        industry: Brand industry context (required)
        audience: Brand audience context (required)
        vibe: Brand vibe context (required)
        conversation_id: Conversation ID for S3 organization
        upload_to_s3: Whether to upload generated images to S3
    
    Returns:
        Result with confirmation of all 4 generated images
    """
    with langsmith.trace(
        name="validate_inputs",
        inputs={
            "person_image_url": person_image_url,
            "product_image_url": product_image_url,
            "base_intent": base_intent
        },
        tags=["validation", "s3-urls"]
    ) as validate_trace:
        if not person_image_url.startswith('http'):
            error_msg = f"Invalid person image URL: {person_image_url}"
            validate_trace.outputs = {"error": error_msg}
            return error_msg

        if not product_image_url.startswith('http'):
            error_msg = f"Invalid product image URL: {product_image_url}"
            validate_trace.outputs = {"error": error_msg}
            return error_msg

        validate_trace.outputs = {"status": "validated", "uses_s3_urls": True}

    # Create both agents
    with langsmith.trace(
        name="create_agents",
        tags=["agent-creation"]
    ) as agent_trace:
        prompt_agent = create_prompt_agent()
        image_agent = create_image_generator_agent()
        agent_trace.outputs = {"agents": ["PromptAgent", "ImageGeneratorAgent"]}

    # Create Task 1: Generate 4 prompts
    brand_context_note = f"""
Brand context (LOCKED):
- Industry: {industry}
- Audience: {audience}
- Vibe: {vibe}
"""
    
    with langsmith.trace(
        name="create_prompt_task",
        inputs={
            "base_intent": base_intent,
            "person_image_url": person_image_url,
            "product_image_url": product_image_url,
            "brand_context": {"industry": industry, "audience": audience, "vibe": vibe}
        },
        tags=["task-creation", "prompt-generation"]
    ) as task1_trace:
        task1 = Task(
            description=f"""Generate 4 diverse UGC prompts by analyzing the person and product images.
{brand_context_note}
Base intent: "{base_intent}"
Person image URL: "{person_image_url}"
Product image URL: "{product_image_url}"

Call the "UGC Prompt Variator" tool ONCE with these parameters:
- base_intent: "{base_intent}"
- person_image_url: "{person_image_url}"
- product_image_url: "{product_image_url}"
- industry: "{industry}"
- audience: "{audience}"
- vibe: "{vibe}"

The tool will analyze both images and return 4 prompts based on what it sees.

After receiving the prompts, your task is complete. Output the 4 prompts clearly.""",
            expected_output="4 diverse UGC prompts clearly listed and numbered 1-4",
            agent=prompt_agent,
            human_input=False
        )
        task1_trace.outputs = {"task": "prompt_generation"}

    # Create Task 2: Generate 4 images (depends on Task 1)
    with langsmith.trace(
        name="create_image_task",
        inputs={
            "person_image_url": person_image_url,
            "product_image_url": product_image_url,
            "conversation_id": conversation_id,
            "upload_to_s3": upload_to_s3
        },
        tags=["task-creation", "image-generation"]
    ) as task2_trace:
        task2 = Task(
            description=f"""The previous task provided 4 prompts. Generate 4 UGC images using those prompts.

Person image URL: {person_image_url}
Product image URL: {product_image_url}
Conversation ID: {conversation_id}

Call the "Banana UGC Image Generator" tool ONCE with these parameters:
- person_image_url: "{person_image_url}"
- product_image_url: "{product_image_url}"
- prompts: [all 4 prompts from previous task as a list]
- conversation_id: "{conversation_id}"
- upload_to_s3: {upload_to_s3}

The tool will generate all 4 images in parallel using S3 URLs directly (no file I/O).

IMPORTANT: After the tool completes, return the EXACT tool output without modification.
The tool output contains [S3_URLS] markers that must be preserved.""",
            expected_output="The exact tool output including [S3_URLS] markers and all 4 S3 URLs",
            agent=image_agent,
            human_input=False,
            context=[task1]  # Task 2 depends on Task 1 output
        )
        task2_trace.outputs = {"task": "image_generation", "s3_enabled": upload_to_s3}

    # Execute crew with sequential tasks
    with langsmith.trace(
        name="execute_crew",
        tags=["crew-execution", "crewai", "sequential"],
        metadata={"agents": 2, "tasks": 2, "workflow": "sequential", "expected_images": 4}
    ) as crew_trace:
        crew = Crew(
            agents=[prompt_agent, image_agent],
            tasks=[task1, task2],  # Sequential: task1 → task2
            verbose=True,
            process="sequential",  # Enforce sequential execution
            full_output=False
        )

        import time
        start_time = time.time()
        
        print("\n" + "="*60)
        print("Starting 2-Agent Sequential Workflow (S3 URLs)")
        print("Agent 1: Prompt Variator → Agent 2: Image Generator")
        print("="*60 + "\n")
        
        result = crew.kickoff()
        execution_time = time.time() - start_time

        crew_trace.metadata["execution_time_seconds"] = round(execution_time, 2)
        crew_trace.outputs = {"result": str(result)}
        
        print("\n" + "="*60)
        print(f"2-Agent workflow completed in {execution_time:.2f} seconds")
        print("="*60 + "\n")
    
    # Parse S3 URLs from result
    result_str = str(result)
    s3_urls = []
    
    print("\n" + "="*60)
    print("DEBUG: Parsing S3 URLs from result")
    print("="*60)
    
    if "[S3_URLS]" in result_str and "[/S3_URLS]" in result_str:
        # Extract S3 URLs from structured response
        start_marker = result_str.find("[S3_URLS]") + len("[S3_URLS]")
        end_marker = result_str.find("[/S3_URLS]")
        urls_section = result_str[start_marker:end_marker].strip()
        
        print(f"Found [S3_URLS] markers")
        print(f"URLs section:\n{urls_section}\n")
        
        s3_urls = [url.strip() for url in urls_section.split('\n') if url.strip().startswith('https://')]
        
        print(f"Extracted {len(s3_urls)} URLs:")
        for idx, url in enumerate(s3_urls, 1):
            print(f"  {idx}. {url}")
    else:
        print("WARNING: [S3_URLS] markers not found in result!")
        print(f"Result preview: {result_str[:500]}...")
    
    print("="*60 + "\n")
    
    # Return structured response
    return {
        "message": result_str,
        "generated_images": s3_urls,
        "execution_time": execution_time
    }
