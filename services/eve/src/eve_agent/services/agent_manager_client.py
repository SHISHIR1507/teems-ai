"""
Agent Manager Client Service
HTTP client for interacting with agent-manager service to check agent assignments
"""
import httpx
from typing import Optional
from loguru import logger
from ..core.config import get_settings

settings = get_settings()


async def check_agent_assignment(
    tenant_id: str,
    user_id: str,
    agent_manager_id: str,
    auth_token: str
) -> bool:
    """
    Check if an agent is assigned to the user's team via agent-manager service.
    
    Args:
        tenant_id: Tenant ID from authenticated user
        user_id: User ID (sub) from authenticated user
        agent_manager_id: UUID of the agent in agent-manager
        auth_token: Auth0 JWT token for authentication
    
    Returns:
        True if agent is assigned to user, False otherwise (or if check fails)
    """
    agent_manager_url = settings.agent_manager_url
    if not agent_manager_url:
        logger.warning("AGENT_MANAGER_URL not configured - cannot check agent assignment")
        return False
    
    # Construct URL
    url = f"{agent_manager_url}/api/agents/{agent_manager_id}"
    
    # Prepare headers with auth token
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code == 404:
                logger.warning(f"Agent {agent_manager_id} not found in agent-manager")
                return False
            
            response.raise_for_status()
            data = response.json()
            
            # Check is_assigned_to_current_user field
            is_assigned = data.get("is_assigned_to_current_user", False)
            return bool(is_assigned)
            
    except httpx.TimeoutException:
        logger.warning(f"Timeout checking agent assignment for {agent_manager_id}")
        return False
    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP error checking agent assignment: {e.response.status_code} - {e.response.text}")
        return False
    except Exception as e:
        logger.warning(f"Error checking agent assignment for {agent_manager_id}: {e}")
        return False


async def get_agent_details(
    agent_manager_id: str,
    auth_token: str
) -> Optional[dict]:
    """
    Get agent details from agent-manager service.
    
    Args:
        agent_manager_id: UUID of the agent in agent-manager
        auth_token: Auth0 JWT token for authentication
    
    Returns:
        Agent details dict or None if not found/error
    """
    agent_manager_url = settings.agent_manager_url
    if not agent_manager_url:
        logger.warning("AGENT_MANAGER_URL not configured - cannot get agent details")
        return None
    
    url = f"{agent_manager_url}/api/agents/{agent_manager_id}"
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code == 404:
                return None
            
            response.raise_for_status()
            return response.json()
            
    except Exception as e:
        logger.warning(f"Error getting agent details for {agent_manager_id}: {e}")
        return None
