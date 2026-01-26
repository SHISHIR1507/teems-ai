"""
Task status endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db_session
from app.core.auth import AuthenticatedUser, require_tenant
from app.models.schemas import TaskStatusResponse
from app.services.db_helpers import get_task, verify_task_ownership
from app.services.slidespeak_client import get_slidespeak_client

router = APIRouter()


@router.get("/v1/tasks/{task_id}/status", response_model=TaskStatusResponse, tags=["tasks"])
async def get_task_status(
    task_id: str,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """Check the status of an async task (tenant verified)"""
    try:
        tenant_id = user.tenant_id
        
        # First check database with tenant verification
        task = await get_task(session, task_id, tenant_id)
        
        if not task:
            # Try to get from SlideSpeak directly (but still require tenant)
            # This shouldn't happen in normal flow, but handle gracefully
            raise HTTPException(status_code=404, detail="Task not found")
        
        # If task is still pending/processing, check with SlideSpeak
        if task.status in ["pending", "processing"]:
            try:
                client = get_slidespeak_client()
                slidespeak_result = client.get_task_status(task.slidespeak_task_id)
                
                status = slidespeak_result.get("status") or slidespeak_result.get("data", {}).get("status", "unknown")
                
                # Update task if status changed
                if status.lower() in ["success", "completed"]:
                    from app.services.db_helpers import update_task
                    await update_task(
                        session,
                        task.id,
                        tenant_id,
                        status="completed",
                        result=slidespeak_result
                    )
                    task.status = "completed"
                    task.result = slidespeak_result
                elif status.lower() in ["failed"]:
                    from app.services.db_helpers import update_task
                    error = slidespeak_result.get("error") or "Unknown error"
                    await update_task(
                        session,
                        task.id,
                        tenant_id,
                        status="failed",
                        error=str(error)
                    )
                    task.status = "failed"
                    task.error = str(error)
            except:
                pass  # Continue with database status
        
        return TaskStatusResponse(
            task_id=task.id,
            status=task.status,
            result=task.result,
            error=task.error,
            created_at=task.created_at.isoformat() if task.created_at else "",
            updated_at=task.updated_at.isoformat() if task.updated_at else ""
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
