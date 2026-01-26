"""
CrewAI Tools for Brand Customization and Task Status
"""
from crewai.tools import tool
from app.services.slidespeak_client import get_slidespeak_client


@tool
def check_task_status(task_id: str) -> str:
    """
    Check the status of an async task (presentation generation, editing, etc.).
    
    Use this tool to check if a task has completed. Tasks typically take 20-30 seconds.
    
    Args:
        task_id: The task ID returned from generation or editing operations (required)
    
    Returns:
        Task status and result information
    """
    try:
        client = get_slidespeak_client()
        result = client.get_task_status(task_id=task_id)
        
        status = result.get("status") or result.get("data", {}).get("status", "unknown")
        
        if status == "SUCCESS" or status == "completed":
            presentation_id = result.get("presentation_id") or result.get("data", {}).get("presentation_id")
            download_url = result.get("download_url") or result.get("data", {}).get("download_url")
            
            response = f"""✅ Task completed successfully!

Task ID: {task_id}
Status: {status}"""
            
            if presentation_id:
                response += f"\nPresentation ID: {presentation_id}"
            
            if download_url:
                response += f"\nDownload URL: {download_url}"
            
            return response
            
        elif status == "PENDING" or status == "pending" or status == "processing":
            return f"""⏳ Task is still processing...

Task ID: {task_id}
Status: {status}

Please wait and check again in a few moments using check_task_status with task_id="{task_id}"."""
            
        elif status == "FAILED" or status == "failed":
            error = result.get("error") or result.get("data", {}).get("error", "Unknown error")
            return f"""❌ Task failed

Task ID: {task_id}
Status: {status}
Error: {error}"""
        else:
            return f"""Task Status:

Task ID: {task_id}
Status: {status}

Full response: {result}"""
        
    except Exception as e:
        return f"❌ Failed to check task status: {str(e)}"


@tool
def get_api_credits() -> str:
    """
    Get the current API credits/usage information.
    
    Use this tool when the user asks about credits, usage, or account information.
    
    Returns:
        User info and remaining credits
    """
    try:
        client = get_slidespeak_client()
        result = client.get_me()
        
        username = result.get("username") or result.get("data", {}).get("username", "Unknown")
        credits = result.get("credits") or result.get("data", {}).get("credits", "Unknown")
        
        return f"""Account Information:

Username: {username}
Remaining Credits: {credits}

You can use these credits to generate presentations."""
        
    except Exception as e:
        return f"❌ Failed to get API credits: {str(e)}"


@tool
def get_presentation_download_url(presentation_id: str) -> str:
    """
    Get a download URL for a completed presentation.
    
    Use this tool when the user wants to download a presentation.
    The download URL is typically short-lived (expires quickly).
    
    Args:
        presentation_id: The SlideSpeak presentation ID (required)
    
    Returns:
        Download URL for the presentation
    """
    try:
        client = get_slidespeak_client()
        result = client.get_download_url(presentation_id=presentation_id)
        
        download_url = result.get("download_url") or result.get("data", {}).get("download_url")
        
        if not download_url:
            return f"❌ No download URL found. Response: {result}"
        
        return f"""✅ Download URL generated!

Presentation ID: {presentation_id}
Download URL: {download_url}

Note: This URL is short-lived and will expire soon. Download the presentation promptly."""
        
    except Exception as e:
        return f"❌ Failed to get download URL: {str(e)}"
