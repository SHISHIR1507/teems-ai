"""
Avatar management endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from app.config.avatars import get_all_avatars, get_avatar_s3_url, avatar_exists

router = APIRouter()


@router.get("/v1/avatars/list", tags=["avatars"])
async def list_avatars() -> Dict[str, Any]:
    """
    Get list of all available avatars with their details
    
    Returns:
        Dictionary containing all avatars with their S3 URLs and voice information
    """
    try:
        avatars = get_all_avatars()
        
        if not avatars:
            raise HTTPException(
                status_code=500,
                detail="Avatar configuration not loaded"
            )
        
        # Format response for frontend
        avatar_list = []
        for avatar_id, avatar_data in avatars.items():
            avatar_list.append({
                "id": int(avatar_id),
                "name": avatar_data.get("name"),
                "preview_url": avatar_data.get("s3_url"),
                "voice_name": avatar_data.get("voice_name"),
                "description": avatar_data.get("description")
            })
        
        # Sort by ID
        avatar_list.sort(key=lambda x: x["id"])
        
        return {
            "avatars": avatar_list,
            "total": len(avatar_list)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve avatars: {str(e)}"
        )


@router.get("/v1/avatars/{avatar_id}", tags=["avatars"])
async def get_avatar_details(avatar_id: int) -> Dict[str, Any]:
    """
    Get details of a specific avatar by ID
    
    Args:
        avatar_id: Avatar ID (1-9)
        
    Returns:
        Avatar details including S3 URL and voice information
    """
    try:
        if not avatar_exists(avatar_id):
            raise HTTPException(
                status_code=404,
                detail=f"Avatar with ID {avatar_id} not found"
            )
        
        avatars = get_all_avatars()
        avatar_data = avatars.get(str(avatar_id))
        
        return {
            "id": avatar_id,
            "name": avatar_data.get("name"),
            "preview_url": avatar_data.get("s3_url"),
            "voice_name": avatar_data.get("voice_name"),
            "custom_voice_id": avatar_data.get("custom_voice_id"),
            "description": avatar_data.get("description")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve avatar: {str(e)}"
        )
