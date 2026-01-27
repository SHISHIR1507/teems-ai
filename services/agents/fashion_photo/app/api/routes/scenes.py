"""
Scenes router - Scene suggestion
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db_session
from app.core.auth import AuthenticatedUser, require_tenant
from app.models.schemas import SceneSuggestionRequest, SceneSuggestionResponse
from app.services.db_helpers import get_session, get_session_apparel, get_session_avatars
from app.orchestrator.fashion_orchestrator import suggest_scenes_orchestrated
from app.services.realtime_notifier import (
    notify_scene_suggestion_started,
    notify_scene_suggestion_completed,
)
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger("routes.scenes")


@router.post("/v1/scenes/suggest", response_model=SceneSuggestionResponse, tags=["scenes"])
async def suggest_scenes(
    request: SceneSuggestionRequest,
    user: AuthenticatedUser = Depends(require_tenant()),
    db: AsyncSession = Depends(get_db_session)
) -> SceneSuggestionResponse:
    """
    Get AI-suggested creative scenes based on uploaded apparel.
    
    The agent analyzes the apparel style and suggests 3 distinct, vivid scene descriptions.
    """
    try:
        tenant_id = user.tenant_id
        session_id = request.session_id
        
        # Verify session exists
        fashion_session = await get_session(db, session_id, tenant_id)
        if not fashion_session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get apparel
        apparel = await get_session_apparel(db, session_id, tenant_id)
        avatars = await get_session_avatars(db, session_id, tenant_id)
        if not apparel:
            raise HTTPException(status_code=400, detail="No apparel found. Please upload apparel first.")
        
        apparel_urls = [a.s3_url for a in apparel]
        avatar_urls = [a.s3_url for a in avatars]
        visual_analysis = apparel[0].vision_analysis if apparel else None
        
        # Notify scene suggestion started
        await notify_scene_suggestion_started(tenant_id, session_id)
        
        result = suggest_scenes_orchestrated(
            apparel_urls=apparel_urls,
            avatar_urls=avatar_urls,
            visual_analysis=visual_analysis,
        )
        
        # Notify completion
        scene_json = result.get("scene_json", {})
        success = result.get("status") == "success"
        error = None if success else result.get("message", "Scene suggestion failed")
        await notify_scene_suggestion_completed(
            tenant_id, session_id, scene_json, success=success, error=error
        )
        
        return SceneSuggestionResponse(
            scenes=result.get("scenes", []),
            message=result.get("message", ""),
            status=result.get("status", "success"),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in scene suggestion: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
