"""
Nylas webhook endpoints
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import json
import logging

from app.core.dependencies import get_db_session
from app.services.db_helpers import (
    get_call_by_nylas_id,
    get_call_by_title,
    update_call,
    delete_call_chunks,
    create_call_chunk
)
from app.services.nylas_service import nylas_service
from app.services.rag_service import rag_service
from app.services.chunker import chunk_text_for_rag
from app.services.embeddings import embedder
from app.services.notification_service import (
    notify_meeting_processing_started,
    notify_meeting_processing_completed,
    notify_call_status_updated
)

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory webhook event log (for debugging)
webhook_events = []


@router.get("/v1/webhooks/nylas", tags=["webhooks"])
async def nylas_webhook_get(request: Request, challenge: str = None):
    """
    Handle GET requests for webhook verification.
    Nylas sends: GET /v1/webhooks/nylas?challenge=xxx
    """
    logger.info(f"Webhook verification request: challenge={challenge}")
    
    if challenge:
        # Return the challenge as PLAIN TEXT (not JSON)
        return Response(
            content=challenge,
            media_type="text/plain",
            headers={"Content-Type": "text/plain"}
        )
    
    # If no challenge, just return OK
    return Response(content="OK", media_type="text/plain")


@router.post("/v1/webhooks/nylas", tags=["webhooks"])
async def nylas_webhook_post(
    request: Request,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Handle POST requests for actual webhook events from Nylas.
    
    This endpoint processes notetaker.media events and:
    - Fetches transcripts, summaries, and action items
    - Processes transcripts for RAG (chunking and embeddings)
    - Updates call records with the processed data
    """
    try:
        # Read the raw body first for logging
        body_bytes = await request.body()
        body_str = body_bytes.decode()
        
        # Parse JSON
        try:
            payload = json.loads(body_str) if body_str else {}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in webhook payload: {e}")
            return Response(
                content="Invalid JSON",
                media_type="text/plain",
                status_code=400
            )
        
        # Check if this is a POST challenge
        if "challenge" in payload:
            logger.info(f"POST Challenge received: {payload['challenge']}")
            return Response(
                content=payload["challenge"],
                media_type="text/plain",
                headers={"Content-Type": "text/plain"}
            )
        
        # Handle actual webhook events
        event_type = payload.get("type", "")
        logger.info(f"Webhook event received: {event_type}")
        
        # Store event for debugging (keep last 50)
        webhook_events.append(payload)
        if len(webhook_events) > 50:
            webhook_events.pop(0)
        
        # Process notetaker events
        if "notetaker.media" in event_type:
            logger.info(f"Processing notetaker media event: {event_type}")
            
            data = payload.get("data", {})
            object_data = data.get("object", {})
            
            # Get Nylas meeting ID
            nylas_meeting_id = object_data.get("id")
            meeting_name = object_data.get("name", "Unknown Meeting")
            
            if not nylas_meeting_id:
                logger.warning("No meeting ID found in webhook payload")
                return Response(content="OK", media_type="text/plain")
            
            # Find meeting in database (try multiple methods)
            call = None
            
            # 1. Try by Nylas meeting_id
            call = await get_call_by_nylas_id(session, nylas_meeting_id)
            
            # 2. Try by title if not found
            if not call:
                logger.info(f"No meeting found by Nylas ID, trying by title: '{meeting_name}'")
                call = await get_call_by_title(session, meeting_name)
            
            if not call:
                logger.warning(
                    f"No meeting found for Nylas ID: {nylas_meeting_id}, "
                    f"Meeting name: '{meeting_name}'"
                )
                return Response(content="OK", media_type="text/plain")
            
            logger.info(f"Found meeting: '{call.title}' (ID: {call.id})")
            
            # Check if already processed
            if call.transcript and len(call.transcript) > 100:
                logger.info(f"Meeting already processed ({len(call.transcript)} chars), skipping")
                return Response(content="OK", media_type="text/plain")
            
            # Notify processing started
            await notify_meeting_processing_started(call.tenant_id, call.id, call.title)
            
            # Update meeting_id if needed
            if not call.meeting_id or call.meeting_id != nylas_meeting_id:
                await update_call(
                    session=session,
                    call_id=call.id,
                    tenant_id=call.tenant_id,
                    meeting_id=nylas_meeting_id,
                    status="processing"
                )
                logger.info(f"Updated meeting with Nylas ID: {nylas_meeting_id}")
            
            # Get media URLs
            media = object_data.get("media", {})
            
            # Fetch and save transcript
            transcript_url = media.get("transcript")
            if transcript_url:
                try:
                    logger.info("Fetching transcript from Nylas")
                    transcript_data = nylas_service.fetch_json_media_url(transcript_url)
                    
                    if transcript_data:
                        # Extract clean text
                        clean_transcript_text = ""
                        
                        if isinstance(transcript_data, dict) and "transcript" in transcript_data:
                            transcript_array = transcript_data["transcript"]
                            if isinstance(transcript_array, list):
                                lines = []
                                for turn in transcript_array:
                                    speaker = turn.get("speaker", "Speaker")
                                    text = turn.get("text", "")
                                    lines.append(f"{speaker}: {text}")
                                clean_transcript_text = "\n".join(lines)
                        
                        elif isinstance(transcript_data, list):
                            lines = []
                            for turn in transcript_data:
                                if isinstance(turn, dict):
                                    speaker = turn.get("speaker", "Speaker")
                                    text = turn.get("text", "")
                                    lines.append(f"{speaker}: {text}")
                            clean_transcript_text = "\n".join(lines)
                        
                        if clean_transcript_text:
                            # Update call with transcript
                            await update_call(
                                session=session,
                                call_id=call.id,
                                tenant_id=call.tenant_id,
                                transcript=clean_transcript_text
                            )
                            logger.info(f"Saved transcript: {len(clean_transcript_text)} chars")
                            
                            # Process for RAG
                            try:
                                # Delete existing chunks if any
                                await delete_call_chunks(session, call.id)
                                
                                # Chunk transcript
                                chunks = chunk_text_for_rag(clean_transcript_text)
                                
                                if chunks:
                                    # Get embeddings
                                    embeddings = await embedder.embed(chunks)
                                    
                                    # Save chunks with embeddings
                                    for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                                        await create_call_chunk(
                                            session=session,
                                            call_id=call.id,
                                            tenant_id=call.tenant_id,
                                            chunk_index=idx,
                                            content=chunk,
                                            embedding=embedding,
                                            content_type="transcript"
                                        )
                                    
                                    logger.info(f"Created {len(chunks)} RAG chunks with embeddings")
                            except Exception as e:
                                logger.error(f"RAG processing failed: {e}", exc_info=True)
                                # Don't fail the webhook if RAG processing fails
                        
                except Exception as e:
                    logger.error(f"Error fetching transcript: {e}", exc_info=True)
            
            # Fetch summary
            summary_url = media.get("summary")
            if summary_url:
                try:
                    logger.info("Fetching summary from Nylas")
                    summary_text = nylas_service.fetch_media_url(summary_url)
                    if summary_text:
                        # Truncate if too long
                        summary_text = summary_text[:5000] if len(summary_text) > 5000 else summary_text
                        await update_call(
                            session=session,
                            call_id=call.id,
                            tenant_id=call.tenant_id,
                            summary=summary_text
                        )
                        logger.info(f"Saved summary: {len(summary_text)} chars")
                except Exception as e:
                    logger.error(f"Error fetching summary: {e}", exc_info=True)
            
            # Fetch action items
            action_items_url = media.get("action_items")
            if action_items_url:
                try:
                    logger.info("Fetching action items from Nylas")
                    action_items_data = nylas_service.fetch_json_media_url(action_items_url)
                    if action_items_data:
                        await update_call(
                            session=session,
                            call_id=call.id,
                            tenant_id=call.tenant_id,
                            action_items=action_items_data
                        )
                        logger.info("Saved action items")
                except Exception as e:
                    logger.error(f"Error fetching action items: {e}", exc_info=True)
            
            # Mark as completed
            await update_call(
                session=session,
                call_id=call.id,
                tenant_id=call.tenant_id,
                status="completed"
            )
            
            # Notify processing completed
            has_transcript = bool(call.transcript and len(call.transcript) > 100)
            has_summary = bool(call.summary)
            has_action_items = bool(call.action_items)
            
            await notify_meeting_processing_completed(
                call.tenant_id,
                call.id,
                has_transcript,
                has_summary,
                has_action_items
            )
            
            # Notify status update
            await notify_call_status_updated(call.tenant_id, call.id, "completed", call.title)
            
            logger.info(f"Successfully processed meeting: {call.title}")
        
        return Response(content="OK", media_type="text/plain")
    
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return Response(
            content="Error processing webhook",
            media_type="text/plain",
            status_code=500
        )
