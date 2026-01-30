"""
Brand sync endpoint
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
    from pyshared.ids import resolve_conversation_id
except ImportError:
    # Fallback if shared libs not available
    def raise_standard_error(status_code, message, detail=None, field=None):
        raise HTTPException(status_code=status_code, detail=message)
    def resolve_conversation_id(value):
        import uuid
        return value if (value and value.strip() and value.strip().lower() not in {"string", "optional-uuid", "uuid"}) else str(uuid.uuid4())
from sqlalchemy.ext.asyncio import AsyncSession
from langsmith import Client, traceable
import langsmith
import os
from datetime import datetime

from app.core.dependencies import get_db_session
from app.core.auth import AuthenticatedUser, require_tenant
from app.models.schemas import BrandSyncRequest, BrandSyncResponse
from app.services import db_helpers
from app.services.realtime_notifier import (
    notify_job_started,
    notify_job_completed,
    notify_job_error
)
from app.orchestrator.ugc_orchestrator import handle_brand_sync
from app.core.config import LANGCHAIN_PROJECT

router = APIRouter()
# Initialize LangSmith client with error handling
try:
    langsmith_client = Client()
except Exception as e:
    print(f"Warning: Failed to initialize LangSmith client: {e}. LangSmith features will be disabled.")
    langsmith_client = None


@router.post("/v1/brand/sync", response_model=BrandSyncResponse, tags=["brand-sync"])
@traceable(name="brand_sync_endpoint", tags=["fastapi", "brand-sync"])
async def brand_sync_endpoint(
    request: BrandSyncRequest,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Brand sync endpoint - stores brand context in database
    
    Requires authentication with tenant_id.
    Locks brand context (industry, audience, vibe) for the conversation.
    """
    try:
        tenant_id = user.tenant_id
        user_id = user.sub
        conversation_id = resolve_conversation_id(request.conversation_id)
        
        # Notify job started
        await notify_job_started(
            tenant_id,
            conversation_id,
            "brand_sync",
            {
                "industry": request.industry,
                "audience": request.audience,
                "vibe": request.vibe
            }
        )
        
        # Get or create conversation with tenant isolation
        conversation = await db_helpers.get_conversation(session, conversation_id, tenant_id)
        was_already_synced = False
        
        if not conversation:
            conversation = await db_helpers.create_conversation(
                session,
                conversation_id,
                tenant_id,
                user_id,
                brand_industry=request.industry,
                brand_audience=request.audience,
                brand_vibe=request.vibe,
                brand_locked=True
            )
            # Update product name
            await db_helpers.update_product_name(session, conversation_id, tenant_id, request.product_name)
        else:
            # Check if brand was already synced
            was_already_synced = conversation.brand_locked if hasattr(conversation, 'brand_locked') else False
            
            # Verify ownership before updating
            if not await db_helpers.verify_conversation_ownership(session, conversation_id, tenant_id):
                await notify_job_error(
                    tenant_id,
                    conversation_id,
                    "brand_sync",
                    "Access denied to this conversation"
                )
                raise_standard_error(
                    status_code=403,
                    message="Access denied",
                    detail="Access denied to this conversation"
                )
            
            conversation = await db_helpers.update_conversation_brand(
                session,
                conversation_id,
                tenant_id,
                request.industry,
                request.audience,
                request.vibe
            )
            # Update product name
            await db_helpers.update_product_name(session, conversation_id, tenant_id, request.product_name)
        
        # Add system message
        await db_helpers.add_message(
            session,
            conversation_id,
            tenant_id,
            "system",
            f"Brand sync: {request.industry} | {request.audience} | {request.vibe} | Product: {request.product_name}"
        )
        
        run_tree = langsmith.get_current_run_tree()
        
        print(f"\n{'='*60}")
        print(f"Brand Sync: {conversation_id} (Tenant: {tenant_id})")
        print(f"Industry: {request.industry}, Audience: {request.audience}, Vibe: {request.vibe}")
        print(f"{'='*60}\n")
        
        # Call orchestrator's brand sync handler
        kai_response = handle_brand_sync(
            industry=request.industry,
            audience=request.audience,
            vibe=request.vibe
        )
        kai_response_str = str(kai_response)
        
        # Add Kai's response to database
        await db_helpers.add_message(session, conversation_id, tenant_id, "assistant", kai_response_str)
        
        # Get trace URL
        trace_url = None
        if run_tree and run_tree.id and langsmith_client:
            try:
                tenant_id_ls = langsmith_client._get_tenant_id()
                project_name = os.getenv("LANGCHAIN_PROJECT", LANGCHAIN_PROJECT)
                trace_url = f"https://smith.langchain.com/o/{tenant_id_ls}/projects/p/{project_name}/r/{run_tree.id}"
            except:
                pass
        
        # Notify job completed
        await notify_job_completed(
            tenant_id,
            conversation_id,
            "brand_sync",
            {
                "kai_response": kai_response_str,
                "brand_locked": True,
                "trace_url": trace_url
            }
        )
        
        return BrandSyncResponse(
            conversation_id=conversation_id,
            kai_response=kai_response_str,
            brand_locked=True,
            timestamp=datetime.now().isoformat(),
            trace_url=trace_url,
            was_already_synced=was_already_synced
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in brand sync: {str(e)}")
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )
        # Notify error
        try:
            await notify_job_error(
                tenant_id,
                conversation_id,
                "brand_sync",
                str(e),
                {"error_type": type(e).__name__}
            )
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
