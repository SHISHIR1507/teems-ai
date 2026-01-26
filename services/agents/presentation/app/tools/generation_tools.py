"""
CrewAI Tools for Presentation Generation
"""
from crewai.tools import tool
from typing import Optional, List, Dict, Any
from app.services.slidespeak_client import get_slidespeak_client


@tool
def generate_presentation_from_text(
    plain_text: str,
    length: int = 6,
    template: str = "default",
    tone: str = "professional",
    verbosity: str = "standard",
    language: str = "ORIGINAL",
    fetch_images: bool = True,
    custom_user_instructions: Optional[str] = None,
    use_branding_logo: bool = False,
    use_branding_color: bool = False
) -> str:
    """
    Generate a PowerPoint presentation from plain text.
    
    Use this tool when the user wants to create a new presentation from text content.
    This is an async operation - it returns a task_id that you should track.
    
    Args:
        plain_text: The content to create presentation from (required)
        length: Number of slides (default: 6, range: 1-50)
        template: Template name (default: "default"). Use get_available_templates() to see options.
        tone: Presentation tone - one of: default, casual, professional, funny, educational, sales_pitch (default: professional)
        verbosity: Content level - one of: concise, standard, text-heavy (default: standard)
        language: Language code or "ORIGINAL" to keep original language (default: ORIGINAL)
        fetch_images: Include stock images (default: True)
        custom_user_instructions: Additional specific requirements (optional)
        use_branding_logo: Apply brand logo if available (default: False)
        use_branding_color: Apply brand colors if available (default: False)
    
    Returns:
        JSON string with task_id and status. Format: {"task_id": "...", "status": "pending", "message": "..."}
    """
    try:
        client = get_slidespeak_client()
        result = client.generate_presentation(
            plain_text=plain_text,
            length=length,
            template=template,
            tone=tone,
            verbosity=verbosity,
            language=language,
            fetch_images=fetch_images,
            custom_user_instructions=custom_user_instructions,
            use_branding_logo=use_branding_logo,
            use_branding_color=use_branding_color
        )
        
        task_id = result.get("task_id") or result.get("data", {}).get("task_id")
        if not task_id:
            return f"❌ Error: No task_id returned from SlideSpeak API. Response: {result}"
        
        return f"""✅ Presentation generation started!

Task ID: {task_id}
Status: pending
Estimated time: 20-30 seconds

The presentation is being generated asynchronously. Use check_task_status tool with task_id="{task_id}" to check progress."""
        
    except Exception as e:
        return f"❌ Failed to generate presentation: {str(e)}"


@tool
def generate_presentation_from_document(
    document_id: str,
    length: int = 6,
    template: str = "default",
    tone: str = "professional",
    verbosity: str = "standard",
    language: str = "ORIGINAL",
    fetch_images: bool = True,
    custom_user_instructions: Optional[str] = None,
    use_branding_logo: bool = False,
    use_branding_color: bool = False
) -> str:
    """
    Generate a PowerPoint presentation from an uploaded document (PDF, Word, etc.).
    
    Use this tool when the user wants to create a presentation from a document that was already uploaded.
    Make sure the document processing is complete before using this tool.
    
    Args:
        document_id: The SlideSpeak document ID from upload_document_to_slidespeak (required)
        length: Number of slides (default: 6)
        template: Template name (default: "default")
        tone: Presentation tone - one of: default, casual, professional, funny, educational, sales_pitch (default: professional)
        verbosity: Content level - one of: concise, standard, text-heavy (default: standard)
        language: Language code or "ORIGINAL" (default: ORIGINAL)
        fetch_images: Include stock images (default: True)
        custom_user_instructions: Additional requirements (optional)
        use_branding_logo: Apply brand logo if available (default: False)
        use_branding_color: Apply brand colors if available (default: False)
    
    Returns:
        JSON string with task_id and status
    """
    try:
        client = get_slidespeak_client()
        result = client.generate_presentation(
            document_id=document_id,
            length=length,
            template=template,
            tone=tone,
            verbosity=verbosity,
            language=language,
            fetch_images=fetch_images,
            custom_user_instructions=custom_user_instructions,
            use_branding_logo=use_branding_logo,
            use_branding_color=use_branding_color
        )
        
        task_id = result.get("task_id") or result.get("data", {}).get("task_id")
        if not task_id:
            return f"❌ Error: No task_id returned. Response: {result}"
        
        return f"""✅ Presentation generation from document started!

Task ID: {task_id}
Status: pending
Document ID: {document_id}
Estimated time: 20-30 seconds

Use check_task_status tool with task_id="{task_id}" to check progress."""
        
    except Exception as e:
        return f"❌ Failed to generate presentation from document: {str(e)}"


@tool
def generate_presentation_slide_by_slide(
    slides: List[Dict[str, Any]],
    template: str = "default"
) -> str:
    """
    Generate a presentation by specifying each slide individually with custom layouts.
    
    Use this tool when the user wants precise control over each slide's content and layout.
    
    Args:
        slides: List of slide objects. Each slide should have:
            - content: The slide content/text
            - layout: Layout type (e.g., "comparison", "items", "timeline", "big-number", "default")
            - language: Optional language code for this slide
        template: Template name (default: "default")
    
    Example slides format:
    [
        {"content": "Introduction to Quantum Computing", "layout": "default"},
        {"content": "Key Concepts: Superposition and Entanglement", "layout": "items"},
        {"content": "Timeline: 2020-2025", "layout": "timeline"}
    ]
    
    Returns:
        JSON string with task_id and status
    """
    try:
        client = get_slidespeak_client()
        result = client.generate_slide_by_slide(slides=slides, template=template)
        
        task_id = result.get("task_id") or result.get("data", {}).get("task_id")
        if not task_id:
            return f"❌ Error: No task_id returned. Response: {result}"
        
        return f"""✅ Slide-by-slide presentation generation started!

Task ID: {task_id}
Status: pending
Number of slides: {len(slides)}
Template: {template}
Estimated time: 20-30 seconds

Use check_task_status tool with task_id="{task_id}" to check progress."""
        
    except Exception as e:
        return f"❌ Failed to generate slide-by-slide presentation: {str(e)}"
