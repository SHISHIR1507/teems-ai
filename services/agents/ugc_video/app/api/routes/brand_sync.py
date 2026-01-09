"""
Brand sync endpoint
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from langsmith import Client, traceable
import langsmith
import os
from datetime import datetime
import uuid

from app.core.dependencies import get_db_session
from app.models.schemas import BrandSyncRequest, BrandSyncResponse
from app.services import db_helpers
from app.orchestrator.ugc_orchestrator import handle_brand_sync
from app.core.config import LANGCHAIN_PROJECT

router = APIRouter()
langsmith_client = Client()


@router.post("/brand-sync", response_model=BrandSyncResponse)
@traceable(name="brand_sync_endpoint", tags=["fastapi", "brand-sync"])
async def brand_sync_endpoint(
    request: BrandSyncRequest,
    session: AsyncSession = Depends(get_db_session)
):
    """Brand sync endpoint - stores brand context in database"""
    conversation_id = request.conversation_id or str(uuid.uuid4())
    
    # Get or create conversation
    conversation = await db_helpers.get_conversation(session, conversation_id)
    if not conversation:
        conversation = await db_helpers.create_conversation(
            session,
            conversation_id,
            brand_industry=request.industry,
            brand_audience=request.audience,
            brand_vibe=request.vibe,
            brand_locked=True
        )
    else:
        conversation = await db_helpers.update_conversation_brand(
            session,
            conversation_id,
            request.industry,
            request.audience,
            request.vibe
        )
    
    # Add system message
    await db_helpers.add_message(
        session,
        conversation_id,
        "system",
        f"Brand sync: {request.industry} | {request.audience} | {request.vibe}"
    )
    
    run_tree = langsmith.get_current_run_tree()
    
    try:
        print(f"\n{'='*60}")
        print(f"Brand Sync: {conversation_id}")
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
        await db_helpers.add_message(session, conversation_id, "assistant", kai_response_str)
        
        # Get trace URL
        trace_url = None
        if run_tree and run_tree.id:
            try:
                tenant_id = langsmith_client._get_tenant_id()
                project_name = os.getenv("LANGCHAIN_PROJECT", LANGCHAIN_PROJECT)
                trace_url = f"https://smith.langchain.com/o/{tenant_id}/projects/p/{project_name}/r/{run_tree.id}"
            except:
                pass
        
        return BrandSyncResponse(
            conversation_id=conversation_id,
            kai_response=kai_response_str,
            brand_locked=True,
            timestamp=datetime.now().isoformat(),
            trace_url=trace_url
        )
        
    except Exception as e:
        print(f"Error in brand sync: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
