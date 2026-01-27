"""
Presentation management endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Query
import sys
from pathlib import Path

# Add shared_libs to path for error standardization
current_file = Path(__file__).resolve()
shared_libs_dir = current_file.parent.parent.parent.parent.parent.parent / "platform" / "shared_libs"
if str(shared_libs_dir) not in sys.path:
    sys.path.insert(0, str(shared_libs_dir))

try:
    from pyshared.errors import raise_standard_error
except ImportError:
    # Fallback if shared libs not available
    def raise_standard_error(status_code, message, detail=None, field=None):
        raise HTTPException(status_code=status_code, detail=message)
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db_session
from app.core.auth import AuthenticatedUser, require_tenant
from app.models.schemas import PresentationResponse, PresentationListResponse
from app.services.db_helpers import (
    get_presentation,
    get_tenant_presentations,
    update_presentation,
    verify_presentation_ownership
)
from app.services.s3_service import generate_presigned_url
from app.services.slidespeak_client import get_slidespeak_client
from sqlalchemy import delete
from app.core.database import Presentation

router = APIRouter()


@router.get("/v1/presentations", response_model=PresentationListResponse, tags=["presentations"])
async def list_presentations(
    user: AuthenticatedUser = Depends(require_tenant()),
    limit: int = Query(20, ge=1, le=100, description="Number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_db_session)
):
    """List tenant's presentations"""
    try:
        tenant_id = user.tenant_id
        presentations = await get_tenant_presentations(session, tenant_id, limit, offset)
        
        # Helper to determine file format from s3_url or default
        def get_file_format(s3_url: Optional[str]) -> Optional[str]:
            if not s3_url:
                return None
            if s3_url.endswith('.pptx'):
                return 'pptx'
            elif s3_url.endswith('.pdf'):
                return 'pdf'
            elif s3_url.endswith('.ppt'):
                return 'ppt'
            return 'pptx'  # Default
        
        return PresentationListResponse(
            presentations=[
                PresentationResponse(
                    id=pres.id,
                    conversation_id=pres.conversation_id,
                    tenant_id=pres.tenant_id,
                    title=pres.title,
                    status=pres.status,
                    s3_url=pres.s3_url,
                    slidespeak_presentation_id=pres.slidespeak_presentation_id,
                    created_at=pres.created_at.isoformat() if pres.created_at else "",
                    updated_at=pres.updated_at.isoformat() if pres.updated_at else "",
                    is_downloadable=pres.status == "completed" and pres.s3_url is not None,
                    file_size=None,  # Could be added to Presentation model if needed
                    file_format=get_file_format(pres.s3_url)
                )
                for pres in presentations
            ],
            total=len(presentations),
            limit=limit,
            offset=offset
        )
    except HTTPException:
        raise
    except Exception as e:
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )


@router.get("/v1/presentations/{presentation_id}", response_model=PresentationResponse, tags=["presentations"])
async def get_presentation_details(
    presentation_id: str,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """Get presentation details (tenant verified)"""
    try:
        tenant_id = user.tenant_id
        presentation = await get_presentation(session, presentation_id, tenant_id)
        if not presentation:
            raise_standard_error(
                status_code=404,
                message="Presentation not found",
                detail=f"Presentation with ID '{presentation_id}' not found for this tenant"
            )
        
        # Helper to determine file format from s3_url or default
        def get_file_format(s3_url: Optional[str]) -> Optional[str]:
            if not s3_url:
                return None
            if s3_url.endswith('.pptx'):
                return 'pptx'
            elif s3_url.endswith('.pdf'):
                return 'pdf'
            elif s3_url.endswith('.ppt'):
                return 'ppt'
            return 'pptx'  # Default
        
        return PresentationResponse(
            id=presentation.id,
            conversation_id=presentation.conversation_id,
            tenant_id=presentation.tenant_id,
            title=presentation.title,
            status=presentation.status,
            s3_url=presentation.s3_url,
            slidespeak_presentation_id=presentation.slidespeak_presentation_id,
            created_at=presentation.created_at.isoformat() if presentation.created_at else "",
            updated_at=presentation.updated_at.isoformat() if presentation.updated_at else "",
            is_downloadable=presentation.status == "completed" and presentation.s3_url is not None,
            file_size=None,  # Could be added to Presentation model if needed
            file_format=get_file_format(presentation.s3_url)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )


@router.get("/v1/presentations/{presentation_id}/download", tags=["presentations"])
async def get_presentation_download(
    presentation_id: str,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """Get presigned download URL for a presentation (tenant verified)"""
    try:
        tenant_id = user.tenant_id
        presentation = await get_presentation(session, presentation_id, tenant_id)
        if not presentation:
            raise_standard_error(
                status_code=404,
                message="Presentation not found",
                detail=f"Presentation with ID '{presentation_id}' not found for this tenant"
            )
        
        if not presentation.s3_key:
            # Try to get from SlideSpeak if we have presentation_id
            if presentation.slidespeak_presentation_id:
                try:
                    client = get_slidespeak_client()
                    result = client.get_download_url(presentation.slidespeak_presentation_id)
                    download_url = result.get("download_url") or result.get("data", {}).get("download_url")
                    if download_url:
                        return {"download_url": download_url, "expires_in": 3600}
                except:
                    pass
            
            raise_standard_error(
                status_code=404,
                message="Presentation file not available",
                detail="Presentation file has not been generated yet or is unavailable"
            )
        
        # Generate presigned URL
        presigned_url = generate_presigned_url(presentation.s3_key, expiration=3600)
        
        return {
            "download_url": presigned_url,
            "expires_in": 3600,
            "presentation_id": presentation_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )


@router.delete("/v1/presentations/{presentation_id}", tags=["presentations"])
async def delete_presentation(
    presentation_id: str,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """Delete a presentation (tenant verified)"""
    try:
        tenant_id = user.tenant_id
        
        # Verify ownership
        if not await verify_presentation_ownership(session, presentation_id, tenant_id):
            raise_standard_error(
                status_code=404,
                message="Presentation not found",
                detail=f"Presentation with ID '{presentation_id}' not found for this tenant"
            )
        
        presentation = await get_presentation(session, presentation_id, tenant_id)
        if not presentation:
            raise_standard_error(
                status_code=404,
                message="Presentation not found",
                detail=f"Presentation with ID '{presentation_id}' not found for this tenant"
            )
        
        # Delete from S3 if exists
        if presentation.s3_key:
            from app.services.s3_service import delete_file_from_s3
            delete_file_from_s3(presentation.s3_key)
        
        # Delete from database
        await session.execute(
            delete(Presentation).where(
                Presentation.id == presentation_id,
                Presentation.tenant_id == tenant_id
            )
        )
        await session.commit()
        
        return {"status": "deleted", "presentation_id": presentation_id}
    except HTTPException:
        raise
    except Exception as e:
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )
