"""
Images router - Generated image management
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db_session
from app.core.auth import AuthenticatedUser, require_tenant
from app.models.schemas import ImageListResponse, GeneratedImageResponse, ImageGenerationRequest, ImageGenerationResponse
from app.services.db_helpers import (
    get_session,
    get_session_avatars,
    get_session_apparel,
    get_session_generated_images,
    count_session_generated_images,
    create_generated_image,
    create_task,
    update_session_metadata,
)
from app.orchestrator.fashion_orchestrator import generate_images_orchestrated
from app.services.s3_service import upload_to_s3
from app.services.realtime_notifier import (
    notify_image_generation_started,
    notify_image_generation_completed,
)
from app.core.logging import get_logger
import re
import uuid as _uuid
import requests

router = APIRouter()
logger = get_logger("routes.images")


@router.post("/v1/images/generate", response_model=ImageGenerationResponse, tags=["images"])
async def generate_images(
    request: ImageGenerationRequest,
    user: AuthenticatedUser = Depends(require_tenant()),
    db: AsyncSession = Depends(get_db_session)
) -> ImageGenerationResponse:
    """
    Generate fashion images from avatars, apparel, and scene description.
    
    This endpoint directly triggers image generation. Alternatively, use the chat endpoint.
    """
    try:
        tenant_id = user.tenant_id
        session_id = request.session_id
        
        # Verify session exists
        fashion_session = await get_session(db, session_id, tenant_id)
        if not fashion_session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        avatars = await get_session_avatars(db, session_id, tenant_id)
        apparel = await get_session_apparel(db, session_id, tenant_id)
        previous_images = await get_session_generated_images(db, session_id, tenant_id, limit=5)
        
        if not avatars:
            raise HTTPException(status_code=400, detail="No avatars found. Please upload or select an avatar first.")
        if not apparel:
            raise HTTPException(status_code=400, detail="No apparel found. Please upload apparel first.")
        
        avatar_urls = [a.s3_url for a in avatars]
        apparel_urls = [a.s3_url for a in apparel]
        previous_urls = [img.s3_url for img in previous_images] if previous_images else None
        if request.previous_image_urls:
            previous_urls = request.previous_image_urls
        
        batch_id = str(_uuid.uuid4())
        task = await create_task(
            db, tenant_id, "image_generation",
            user.sub, session_id, status="processing"
        )
        
        # Extract angles and variations from scene if available (for notification)
        angles_count = 2  # default
        variations = 2  # default
        # Could parse from scene_description or use defaults
        
        # Notify generation started
        await notify_image_generation_started(
            tenant_id, session_id, batch_id,
            request.scene_description, angles_count, variations
        )
        
        result = generate_images_orchestrated(
            scene_description=request.scene_description,
            avatar_urls=avatar_urls,
            apparel_urls=apparel_urls,
            scene_json=None,
            previous_images=previous_urls,
        )
        
        new_gen_urls = []
        if result.get("image_urls"):
            for url in result["image_urls"]:
                try:
                    if "aimlapi" in url or "d144" in url or "generated" in url.lower():
                        img_data = requests.get(url, timeout=30).content
                        s3_permanent_url = upload_to_s3(img_data, "ai_generated", "png")
                        new_gen_urls.append(s3_permanent_url)
                        s3_key = s3_permanent_url.split("/")[-1]
                        await create_generated_image(
                            db, session_id, tenant_id,
                            s3_permanent_url, s3_key,
                            user.sub,
                            scene=request.scene_description,
                            task_id=task.id,
                            batch_id=batch_id,
                            generation_type="initial",
                        )
                except Exception as e:
                    logger.error("Failed to upload gen image to S3: %s - %s", url, e)
                    new_gen_urls.append(url)
        
        from app.services.db_helpers import update_task_status
        await update_task_status(
            db, task.id, tenant_id,
            "completed" if new_gen_urls else "failed",
            result={"image_urls": new_gen_urls} if new_gen_urls else None,
        )
        await update_session_metadata(
            db, session_id, tenant_id,
            {"last_generation_batch_id": batch_id},
        )
        
        # Notify completion
        await notify_image_generation_completed(
            tenant_id, session_id, batch_id, new_gen_urls,
            success=bool(new_gen_urls),
            error=None if new_gen_urls else "No images generated"
        )
        
        return ImageGenerationResponse(
            image_urls=new_gen_urls,
            message=result.get("message", "Image generation completed"),
            status=result.get("status", "success" if new_gen_urls else "failed"),
            task_id=task.id,
            batch_id=batch_id,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in image generation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/images", response_model=ImageListResponse, tags=["images"])
async def list_images(
    session_id: str,
    user: AuthenticatedUser = Depends(require_tenant()),
    db: AsyncSession = Depends(get_db_session),
    limit: int = 100,
    offset: int = 0
) -> ImageListResponse:
    """List generated images for a session"""
    try:
        tenant_id = user.tenant_id
        
        # Verify session exists
        fashion_session = await get_session(db, session_id, tenant_id)
        if not fashion_session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        images = await get_session_generated_images(db, session_id, tenant_id, limit, offset)
        total = await count_session_generated_images(db, session_id, tenant_id)
        
        return ImageListResponse(
            images=[
                GeneratedImageResponse(
                    id=img.id,
                    session_id=img.session_id,
                    s3_url=img.s3_url,
                    angle=img.angle,
                    scene=img.scene,
                    created_at=img.created_at.isoformat()
                )
                for img in images
            ],
            total=total,
            limit=limit,
            offset=offset
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing images: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
