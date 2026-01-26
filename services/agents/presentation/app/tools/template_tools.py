"""
CrewAI Tools for Template Management
"""
from crewai.tools import tool
from app.services.slidespeak_client import get_slidespeak_client


@tool
def get_available_templates() -> str:
    """
    Get a list of all available default templates.
    
    Use this tool when the user asks about templates or wants to see template options.
    Always use this tool before suggesting a template name to ensure accuracy.
    
    Returns:
        List of available templates with their names and descriptions
    """
    try:
        client = get_slidespeak_client()
        result = client.get_templates()
        
        templates = result.get("templates") or result.get("data", {}).get("templates", [])
        
        if not templates:
            return "No templates found. Default template is always available."
        
        template_list = []
        for template in templates:
            name = template.get("name", "Unknown")
            description = template.get("description", "No description")
            template_list.append(f"- {name}: {description}")
        
        return f"""Available Templates:

{chr(10).join(template_list)}

You can use any of these template names when generating presentations.
Default template is always available if no specific template is requested."""
        
    except Exception as e:
        return f"❌ Failed to get templates: {str(e)}"


@tool
def get_branded_templates() -> str:
    """
    Get a list of branded templates (user's custom templates).
    
    Use this tool when the user asks about their branded/custom templates.
    
    Returns:
        List of branded templates
    """
    try:
        client = get_slidespeak_client()
        result = client.get_branded_templates()
        
        templates = result.get("templates") or result.get("data", {}).get("templates", [])
        
        if not templates:
            return "No branded templates found. You can create branded templates through the SlideSpeak dashboard."
        
        template_list = []
        for template in templates:
            name = template.get("name", "Unknown")
            description = template.get("description", "No description")
            template_list.append(f"- {name}: {description}")
        
        return f"""Your Branded Templates:

{chr(10).join(template_list)}

You can use any of these template names when generating presentations."""
        
    except Exception as e:
        return f"❌ Failed to get branded templates: {str(e)}"
