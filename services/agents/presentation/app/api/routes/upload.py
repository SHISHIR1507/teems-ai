"""
File upload endpoint
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
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
from app.models.schemas import UploadRequest, UploadResponse
from app.services.db_helpers import (
    get_or_create_conversation,
    create_document,
    update_document,
    get_document
)
from app.services.s3_service import upload_bytes_to_s3, get_s3_key_for_upload
from app.services.slidespeak_client import get_slidespeak_client
from app.services.realtime_notifier import (
    notify_document_upload_started,
    notify_document_processing_started,
    notify_document_processing_completed
)
import uuid

router = APIRouter()


@router.post("/v1/upload", response_model=UploadResponse, tags=["upload"])
async def upload_document(
    file: UploadFile = File(..., description="Document file (PDF, DOCX, etc.)"),
    conversation_id: str = Form(None, description="Conversation ID (optional)"),
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Upload a document (PDF, Word, etc.) for presentation generation.
    
    Requires authentication with tenant_id.
    
    The document will be:
    1. Uploaded to S3
    2. Uploaded to SlideSpeak for processing
    3. Tracked in the database
    
    Once processing is complete, you can use the document_id to generate a presentation.
    """
    try:
        tenant_id = user.tenant_id
        conversation_id = conversation_id or str(uuid.uuid4())
        
        # Get or create conversation
        conversation = await get_or_create_conversation(
            session, conversation_id, tenant_id, user.sub
        )
        
        # Read file content
        content = await file.read()
        file_size = len(content)
        
        # Upload to S3
        s3_key = get_s3_key_for_upload(conversation_id, file.filename, "document")
        s3_url = upload_bytes_to_s3(
            content,
            s3_key,
            file.content_type or "application/octet-stream",
            public_read=True  # Make public for SlideSpeak to access
        )
        
        # Create document record
        document = await create_document(
            session,
            conversation_id,
            tenant_id,
            user.sub,
            file.filename,
            s3_url,
            s3_key,
            file_size,
            file.content_type
        )
        
        # Notify frontend that upload started
        await notify_document_upload_started(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            document_id=document.id,
            filename=file.filename
        )
        
        # Upload to SlideSpeak
        try:
            client = get_slidespeak_client()
            slidespeak_result = client.upload_document(document_url=s3_url)
            
            slidespeak_document_id = (
                slidespeak_result.get("document_id") or 
                slidespeak_result.get("data", {}).get("document_id")
            )
            
            if slidespeak_document_id:
                # Update document with SlideSpeak ID
                await update_document(
                    session,
                    document.id,
                    tenant_id,
                    slidespeak_document_id=slidespeak_document_id,
                    processing_status="processing"
                )
                
                # Notify frontend that processing started
                await notify_document_processing_started(
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    document_id=document.id,
                    slidespeak_document_id=slidespeak_document_id,
                    filename=file.filename
                )
                
                return UploadResponse(
                    document_id=document.id,
                    filename=file.filename,
                    s3_url=s3_url,
                    processing_status="processing",
                    message=f"Document uploaded successfully. Document ID: {slidespeak_document_id}. Use check_document_processing_status to check when it's ready."
                )
            else:
                # Notify that processing failed
                await notify_document_processing_completed(
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    document_id=document.id,
                    slidespeak_document_id="",
                    success=False,
                    error="SlideSpeak upload may have failed"
                )
                return UploadResponse(
                    document_id=document.id,
                    filename=file.filename,
                    s3_url=s3_url,
                    processing_status="uploaded",
                    message="Document uploaded to S3, but SlideSpeak upload may have failed. Please try again."
                )
        except Exception as e:
            # S3 upload succeeded, but SlideSpeak upload failed
            await notify_document_processing_completed(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                document_id=document.id,
                slidespeak_document_id="",
                success=False,
                error=str(e)
            )
            return UploadResponse(
                document_id=document.id,
                filename=file.filename,
                s3_url=s3_url,
                processing_status="uploaded",
                message=f"Document uploaded to S3, but SlideSpeak upload failed: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )


@router.get("/v1/documents/{document_id}/status", tags=["upload"])
async def get_document_status(
    document_id: str,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get document processing status.
    
    Requires authentication with tenant_id.
    Returns current processing status and any error information.
    """
    try:
        tenant_id = user.tenant_id
        
        document = await get_document(session, document_id, tenant_id)
        
        if not document:
            raise_standard_error(
                status_code=404,
                message="Document not found",
                detail=f"Document with ID '{document_id}' not found for this tenant"
            )
        
        # If still processing, check with SlideSpeak
        if document.processing_status == "processing" and document.slidespeak_document_id:
            try:
                client = get_slidespeak_client()
                # Note: SlideSpeak may not have a document status endpoint
                # This is a placeholder - adjust based on actual SlideSpeak API
                # For now, we return the database status
            except:
                pass  # Continue with database status
        
        return {
            "document_id": document.id,
            "filename": document.filename,
            "processing_status": document.processing_status,
            "slidespeak_document_id": document.slidespeak_document_id,
            "created_at": document.created_at.isoformat() if document.created_at else None,
            "updated_at": document.updated_at.isoformat() if document.updated_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )
