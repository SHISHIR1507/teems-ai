"""
CrewAI Tools for Presentation Editing
"""
from crewai.tools import tool
from typing import Optional, Dict, Any
from app.services.slidespeak_client import get_slidespeak_client


@tool
def edit_presentation(
    presentation_id: str,
    updates: Dict[str, Any]
) -> str:
    """
    Edit an existing presentation by replacing content through key-value JSON configuration.
    
    Use this tool when the user wants to update content in an existing presentation.
    
    Args:
        presentation_id: The SlideSpeak presentation ID (required)
        updates: Dictionary of updates. Format depends on SlideSpeak API requirements.
                 Typically includes content replacements, style changes, etc.
    
    Returns:
        Success message or error
    """
    try:
        client = get_slidespeak_client()
        result = client.edit_presentation(
            presentation_id=presentation_id,
            updates=updates
        )
        
        task_id = result.get("task_id") or result.get("data", {}).get("task_id")
        if task_id:
            return f"""✅ Presentation edit started!

Task ID: {task_id}
Presentation ID: {presentation_id}
Status: pending

Use check_task_status tool with task_id="{task_id}" to check progress."""
        else:
            return f"✅ Presentation edited successfully! Response: {result}"
        
    except Exception as e:
        return f"❌ Failed to edit presentation: {str(e)}"


@tool
def edit_slide(
    presentation_id: str,
    action: str,
    slide_index: Optional[int] = None,
    content: Optional[Dict[str, Any]] = None
) -> str:
    """
    Insert, regenerate, or remove a slide in an existing presentation.
    
    Use this tool when the user wants to modify individual slides.
    
    Args:
        presentation_id: The SlideSpeak presentation ID (required)
        action: Action to perform - one of: "insert", "regenerate", "remove" (required)
        slide_index: Index of the slide (0-based). Required for regenerate and remove.
        content: Content for the new/regenerated slide. Required for insert and regenerate.
                 Format: {"text": "...", "layout": "..."}
    
    Returns:
        Success message with task_id or error
    """
    try:
        if action not in ["insert", "regenerate", "remove"]:
            return f"❌ Invalid action: {action}. Must be one of: insert, regenerate, remove"
        
        if action in ["regenerate", "remove"] and slide_index is None:
            return f"❌ slide_index is required for action: {action}"
        
        if action in ["insert", "regenerate"] and not content:
            return f"❌ content is required for action: {action}"
        
        client = get_slidespeak_client()
        result = client.edit_slide(
            presentation_id=presentation_id,
            action=action,
            slide_index=slide_index,
            content=content
        )
        
        task_id = result.get("task_id") or result.get("data", {}).get("task_id")
        if task_id:
            return f"""✅ Slide {action} started!

Task ID: {task_id}
Presentation ID: {presentation_id}
Action: {action}
Slide Index: {slide_index if slide_index is not None else "N/A"}
Status: pending

Use check_task_status tool with task_id="{task_id}" to check progress."""
        else:
            return f"✅ Slide {action} completed! Response: {result}"
        
    except Exception as e:
        return f"❌ Failed to {action} slide: {str(e)}"
