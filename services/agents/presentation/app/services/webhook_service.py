"""
Webhook service for processing SlideSpeak webhook notifications
"""
from typing import Dict, Any
from app.services.slidespeak_client import get_slidespeak_client
from app.services.s3_service import download_from_url_to_s3, get_s3_key_for_upload
from app.services.db_helpers import (
    get_task_by_slidespeak_id,
    update_task,
    update_presentation
)
from app.services.realtime_notifier import (
    notify_presentation_generation_completed,
    notify_presentation_edit_completed
)
from sqlalchemy.ext.asyncio import AsyncSession


async def process_webhook(
    session: AsyncSession,
    webhook_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Process a webhook notification from SlideSpeak
    
    Args:
        session: Database session
        webhook_data: Webhook payload from SlideSpeak
    
    Returns:
        Processing result
    """
    try:
        event_type = webhook_data.get("event_type") or webhook_data.get("type", "unknown")
        task_id = webhook_data.get("task_id") or webhook_data.get("data", {}).get("task_id")
        
        if not task_id:
            return {"error": "No task_id in webhook data"}
        
        # Find task in database by slidespeak_task_id (webhooks don't have tenant context)
        task = await get_task_by_slidespeak_id(session, task_id)
        
        if not task:
            return {"error": f"Task not found: {task_id}"}
        
        status = webhook_data.get("status") or webhook_data.get("data", {}).get("status", "unknown")
        
        if status == "SUCCESS" or status == "completed":
            # Get presentation info from SlideSpeak
            client = get_slidespeak_client()
            task_status = client.get_task_status(task_id)
            
            presentation_id = (
                task_status.get("presentation_id") or 
                task_status.get("data", {}).get("presentation_id") or
                webhook_data.get("presentation_id")
            )
            
            download_url = (
                task_status.get("download_url") or 
                task_status.get("data", {}).get("download_url")
            )
            
            # Update task (use tenant_id from task)
            await update_task(
                session,
                task.id,
                task.tenant_id,
                status="completed",
                result={"presentation_id": presentation_id, "download_url": download_url}
            )
            
            # If we have a presentation record, update it
            if task.task_type == "generate" and presentation_id:
                # Find presentation by slidespeak_task_id
                from sqlalchemy import select
                from app.core.database import Presentation
                result = await session.execute(
                    select(Presentation).where(Presentation.slidespeak_task_id == task_id)
                )
                presentation = result.scalar_one_or_none()
                
                if presentation and download_url:
                    # Download presentation and upload to S3
                    try:
                        s3_key = get_s3_key_for_upload(
                            presentation.conversation_id,
                            f"{presentation.id}.pptx",
                            "presentation"
                        )
                        s3_url = download_from_url_to_s3(download_url, s3_key, "application/vnd.openxmlformats-officedocument.presentationml.presentation")
                        
                        await update_presentation(
                            session,
                            presentation.id,
                            task.tenant_id,  # Use tenant_id from task
                            status="completed",
                            slidespeak_presentation_id=presentation_id,
                            s3_url=s3_url,
                            s3_key=s3_key
                        )
                        
                        # Notify frontend that generation completed
                        await notify_presentation_generation_completed(
                            tenant_id=task.tenant_id,
                            conversation_id=task.conversation_id or "",
                            task_id=task.slidespeak_task_id,
                            presentation_id=presentation.id,
                            download_url=download_url,
                            s3_url=s3_url,
                            success=True
                        )
                    except Exception as e:
                        print(f"Error downloading/uploading presentation: {e}")
                        await update_presentation(
                            session,
                            presentation.id,
                            task.tenant_id,  # Use tenant_id from task
                            status="completed",
                            slidespeak_presentation_id=presentation_id,
                            error=f"Download failed: {str(e)}"
                        )
                        
                        # Notify frontend that generation failed
                        await notify_presentation_generation_completed(
                            tenant_id=task.tenant_id,
                            conversation_id=task.conversation_id or "",
                            task_id=task.slidespeak_task_id,
                            presentation_id=presentation.id,
                            success=False,
                            error=f"Download failed: {str(e)}"
                        )
            elif task.task_type == "edit":
                # Handle edit completion
                from sqlalchemy import select
                from app.core.database import Presentation
                result = await session.execute(
                    select(Presentation).where(Presentation.slidespeak_task_id == task_id)
                )
                presentation = result.scalar_one_or_none()
                
                if presentation and download_url:
                    try:
                        s3_key = get_s3_key_for_upload(
                            presentation.conversation_id,
                            f"{presentation.id}_edited.pptx",
                            "presentation"
                        )
                        s3_url = download_from_url_to_s3(download_url, s3_key, "application/vnd.openxmlformats-officedocument.presentationml.presentation")
                        
                        await update_presentation(
                            session,
                            presentation.id,
                            task.tenant_id,
                            status="completed",
                            s3_url=s3_url,
                            s3_key=s3_key
                        )
                        
                        # Notify frontend that edit completed
                        await notify_presentation_edit_completed(
                            tenant_id=task.tenant_id,
                            conversation_id=task.conversation_id or "",
                            task_id=task.slidespeak_task_id,
                            presentation_id=presentation.id,
                            download_url=download_url,
                            s3_url=s3_url,
                            success=True
                        )
                    except Exception as e:
                        await notify_presentation_edit_completed(
                            tenant_id=task.tenant_id,
                            conversation_id=task.conversation_id or "",
                            task_id=task.slidespeak_task_id,
                            presentation_id=presentation.id if presentation else "",
                            success=False,
                            error=f"Download failed: {str(e)}"
                        )
            
            return {
                "status": "processed",
                "task_id": task.id,
                "presentation_id": presentation_id,
                "message": "Webhook processed successfully"
            }
            
        elif status == "FAILED" or status == "failed":
            error = webhook_data.get("error") or webhook_data.get("data", {}).get("error", "Unknown error")
            
            await update_task(
                session,
                task.id,
                task.tenant_id,
                status="failed",
                error=error
            )
            
            # Update presentation if exists
            if task.task_type == "generate":
                from sqlalchemy import select
                from app.core.database import Presentation
                result = await session.execute(
                    select(Presentation).where(Presentation.slidespeak_task_id == task_id)
                )
                presentation = result.scalar_one_or_none()
                if presentation:
                    await update_presentation(
                        session,
                        presentation.id,
                        task.tenant_id,
                        status="failed",
                        error=error
                    )
                    
                    # Notify frontend that generation failed
                    await notify_presentation_generation_completed(
                        tenant_id=task.tenant_id,
                        conversation_id=task.conversation_id or "",
                        task_id=task.slidespeak_task_id,
                        presentation_id=presentation.id,
                        success=False,
                        error=error
                    )
            elif task.task_type == "edit":
                # Notify frontend that edit failed
                from sqlalchemy import select
                from app.core.database import Presentation
                result = await session.execute(
                    select(Presentation).where(Presentation.slidespeak_task_id == task_id)
                )
                presentation = result.scalar_one_or_none()
                if presentation:
                    await notify_presentation_edit_completed(
                        tenant_id=task.tenant_id,
                        conversation_id=task.conversation_id or "",
                        task_id=task.slidespeak_task_id,
                        presentation_id=presentation.id,
                        success=False,
                        error=error
                    )
            
            return {
                "status": "processed",
                "task_id": task.id,
                "message": f"Task failed: {error}"
            }
        else:
            # Update status
            await update_task(session, task.id, task.tenant_id, status="processing")
            return {
                "status": "processed",
                "task_id": task.id,
                "message": f"Task status updated to: {status}"
            }
            
    except Exception as e:
        return {
            "error": f"Error processing webhook: {str(e)}"
        }
