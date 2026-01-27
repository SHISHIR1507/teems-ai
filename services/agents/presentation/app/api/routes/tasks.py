"""
Task status endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
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
from app.models.schemas import TaskStatusResponse
from app.services.db_helpers import get_task, verify_task_ownership
from app.services.slidespeak_client import get_slidespeak_client
from app.services.realtime_notifier import notify_task_status_updated

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
            raise_standard_error(
                status_code=404,
                message="Task not found",
                detail=f"Task with ID '{task_id}' not found for this tenant"
            )
        
        # If task is still pending/processing, check with SlideSpeak
        if task.status in ["pending", "processing"]:
            try:
                client = get_slidespeak_client()
                slidespeak_result = client.get_task_status(task.slidespeak_task_id)
                
                status = slidespeak_result.get("status") or slidespeak_result.get("data", {}).get("status", "unknown")
                
                # Update task if status changed
                old_status = task.status
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
                    
                    # Notify frontend if status changed
                    if old_status != "completed":
                        await notify_task_status_updated(
                            tenant_id=tenant_id,
                            conversation_id=task.conversation_id or "",
                            task_id=task.id,
                            status="completed",
                            result=slidespeak_result
                        )
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
                    
                    # Notify frontend if status changed
                    if old_status != "failed":
                        await notify_task_status_updated(
                            tenant_id=tenant_id,
                            conversation_id=task.conversation_id or "",
                            task_id=task.id,
                            status="failed",
                            error=str(error)
                        )
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
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )
