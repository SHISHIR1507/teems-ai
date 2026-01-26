"""
Presentation Orchestrator
Coordinates multi-agent workflows for presentation operations
"""
from crewai import Task, Crew
from app.agents.presentation_specialist import create_presentation_specialist_agent
from app.agents.presentation_generator import create_presentation_generator_agent
from app.agents.presentation_editor import create_presentation_editor_agent
from app.agents.brand_manager import create_brand_manager_agent
from typing import Optional, Dict, Any
import concurrent.futures

# Thread pool for running CrewAI without blocking
executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)


def chat_with_presentation_specialist(message: str, brand_context: Optional[Dict[str, Any]] = None) -> str:
    """
    Handle general chat with the Presentation Specialist agent
    
    Args:
        message: User's message
        brand_context: Optional brand context (logo_url, primary_color, etc.)
    
    Returns:
        Agent's response
    """
    agent = create_presentation_specialist_agent()
    
    context_note = ""
    if brand_context and brand_context.get('locked'):
        context_note = f"""
        
Brand context (already configured):
- Logo URL: {brand_context.get('logo_url', 'Not set')}
- Primary Color: {brand_context.get('primary_color', 'Not set')}
- Secondary Color: {brand_context.get('secondary_color', 'Not set')}
- Font: {brand_context.get('font', 'Not set')}

Reference this naturally if relevant to the conversation."""
    
    task = Task(
        description=f"""Respond to the user's message: "{message}"

Be helpful, friendly, and accurate. Always use tools to get real information - never make up template names, features, or capabilities.
Ask clarifying questions if the user's request is ambiguous or missing required information.{context_note}""",
        expected_output="A helpful, accurate response",
        agent=agent,
        human_input=False
    )
    
    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=True,
        max_iter=5,
        full_output=False
    )
    
    try:
        future = executor.submit(crew.kickoff)
        result = future.result(timeout=120)
        return str(result)
    except concurrent.futures.TimeoutError:
        return "Sorry, the request took too long to process. Please try again."
    except Exception as e:
        return f"Sorry, I encountered an error: {str(e)}"


def generate_presentation_orchestrated(
    user_message: str,
    conversation_id: str,
    tenant_id: str,
    brand_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Orchestrate presentation generation using 2-agent sequential workflow:
    1. Presentation Specialist - understands requirements, asks questions
    2. Presentation Generator - executes generation
    
    Args:
        user_message: User's request
        conversation_id: Conversation ID
        tenant_id: Tenant ID from authenticated user
        brand_context: Optional brand context
    
    Returns:
        Structured response with task_id, status, etc.
    """
    specialist = create_presentation_specialist_agent()
    generator = create_presentation_generator_agent()
    
    brand_note = ""
    if brand_context and brand_context.get('locked'):
        brand_note = f"""
Brand context (LOCKED):
- Logo URL: {brand_context.get('logo_url')}
- Primary Color: {brand_context.get('primary_color')}
- Secondary Color: {brand_context.get('secondary_color')}
- Font: {brand_context.get('font')}

Apply branding when generating (use_branding_logo=True, use_branding_color=True)."""
    
    # Task 1: Understand requirements
    task1 = Task(
        description=f"""Understand the user's presentation generation request: "{user_message}"

Your job:
1. Extract all required information (topic, length, template, tone, etc.)
2. If information is missing, ask clarifying questions
3. Use get_available_templates() to see real template options before suggesting
4. Once you have all information, summarize the requirements clearly

{brand_note}

Output a clear summary of requirements that the Presentation Generator can use.""",
        expected_output="Clear requirements summary with all parameters",
        agent=specialist,
        human_input=False
    )
    
    # Task 2: Generate presentation (depends on task1)
    task2 = Task(
        description=f"""Generate the presentation based on the requirements from the previous task.

Use the appropriate generation tool:
- generate_presentation_from_text if user provided text
- generate_presentation_from_document if user uploaded a document
- generate_presentation_slide_by_slide if user wants custom slide layouts

{brand_note}

Return the task_id from the generation operation.""",
        expected_output="Task ID from presentation generation",
        agent=generator,
        context=[task1],
        human_input=False
    )
    
    crew = Crew(
        agents=[specialist, generator],
        tasks=[task1, task2],
        process="sequential",
        verbose=True,
        full_output=False
    )
    
    try:
        future = executor.submit(crew.kickoff)
        result = future.result(timeout=180)
        result_str = str(result)
        
        # Extract task_id from result
        task_id = None
        if "task_id" in result_str.lower():
            import re
            match = re.search(r'task[_\s]*id[:\s]*([a-zA-Z0-9\-]+)', result_str, re.IGNORECASE)
            if match:
                task_id = match.group(1)
        
        return {
            "message": result_str,
            "task_id": task_id,
            "status": "processing" if task_id else "pending",
            "conversation_id": conversation_id
        }
    except concurrent.futures.TimeoutError:
        return {
            "message": "Sorry, the request took too long to process. Please try again.",
            "task_id": None,
            "status": "failed",
            "conversation_id": conversation_id
        }
    except Exception as e:
        return {
            "message": f"Sorry, I encountered an error: {str(e)}",
            "task_id": None,
            "status": "failed",
            "conversation_id": conversation_id
        }


def edit_presentation_orchestrated(
    user_message: str,
    presentation_id: str,
    conversation_id: str,
    tenant_id: str
) -> Dict[str, Any]:
    """
    Orchestrate presentation editing using 2-agent sequential workflow:
    1. Presentation Specialist - understands edit requirements
    2. Presentation Editor - executes edits
    
    Args:
        user_message: User's edit request
        presentation_id: Presentation ID to edit
        conversation_id: Conversation ID
        tenant_id: Tenant ID from authenticated user
    
    Returns:
        Structured response with task_id, status, etc.
    """
    specialist = create_presentation_specialist_agent()
    editor = create_presentation_editor_agent()
    
    # Task 1: Understand edit requirements
    task1 = Task(
        description=f"""Understand the user's edit request: "{user_message}"

Presentation ID: {presentation_id}

Your job:
1. Understand what the user wants to edit
2. Determine if it's a full presentation edit or a specific slide edit
3. Extract all necessary parameters (slide_index, content, action type)
4. Clarify any ambiguous requests

Output clear edit instructions.""",
        expected_output="Clear edit instructions with all parameters",
        agent=specialist,
        human_input=False
    )
    
    # Task 2: Execute edit (depends on task1)
    task2 = Task(
        description=f"""Execute the edit based on instructions from the previous task.

Presentation ID: {presentation_id}

Use the appropriate editing tool:
- edit_presentation for bulk content updates
- edit_slide for inserting, regenerating, or removing individual slides

Return the task_id from the edit operation.""",
        expected_output="Task ID from presentation edit",
        agent=editor,
        context=[task1],
        human_input=False
    )
    
    crew = Crew(
        agents=[specialist, editor],
        tasks=[task1, task2],
        process="sequential",
        verbose=True,
        full_output=False
    )
    
    try:
        future = executor.submit(crew.kickoff)
        result = future.result(timeout=180)
        result_str = str(result)
        
        # Extract task_id from result
        task_id = None
        if "task_id" in result_str.lower():
            import re
            match = re.search(r'task[_\s]*id[:\s]*([a-zA-Z0-9\-]+)', result_str, re.IGNORECASE)
            if match:
                task_id = match.group(1)
        
        return {
            "message": result_str,
            "task_id": task_id,
            "status": "processing" if task_id else "pending",
            "presentation_id": presentation_id,
            "conversation_id": conversation_id
        }
    except concurrent.futures.TimeoutError:
        return {
            "message": "Sorry, the edit request took too long to process. Please try again.",
            "task_id": None,
            "status": "failed",
            "presentation_id": presentation_id,
            "conversation_id": conversation_id
        }
    except Exception as e:
        return {
            "message": f"Sorry, I encountered an error: {str(e)}",
            "task_id": None,
            "status": "failed",
            "presentation_id": presentation_id,
            "conversation_id": conversation_id
        }


def handle_brand_sync(
    logo_url: Optional[str] = None,
    primary_color: Optional[str] = None,
    secondary_color: Optional[str] = None,
    font: Optional[str] = None
) -> str:
    """
    Handle brand sync - reflect brand understanding back to user
    
    Args:
        logo_url: Brand logo URL
        primary_color: Primary brand color
        secondary_color: Secondary brand color
        font: Brand font
    
    Returns:
        Brand reflection message
    """
    agent = create_brand_manager_agent()
    
    brand_info = []
    if logo_url:
        brand_info.append(f"Logo: {logo_url}")
    if primary_color:
        brand_info.append(f"Primary Color: {primary_color}")
    if secondary_color:
        brand_info.append(f"Secondary Color: {secondary_color}")
    if font:
        brand_info.append(f"Font: {font}")
    
    brand_summary = "\n".join(brand_info) if brand_info else "No brand settings provided"
    
    task = Task(
        description=f"""You are a brand manager. A user has provided brand settings:

{brand_summary}

Reflect the brand back confidently:
- Show you understand the brand identity
- Explain how these settings will be applied to presentations
- Set expectations for brand consistency
- Be confident and professional

Do NOT repeat inputs verbatim. Rephrase and show understanding.""",
        expected_output="Confident brand reflection in natural language",
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
    
    try:
        future = executor.submit(crew.kickoff)
        result = future.result(timeout=60)
        return str(result)
    except Exception as e:
        return f"Brand settings saved. I'll apply these to your presentations going forward."
