from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import json
import requests
from app.core.database import get_db
from app.models.call import Call
from app.services.rag_service import rag_service

router = APIRouter()

webhook_events = []

@router.get("/webhooks/nylas")
async def nylas_webhook_get(request: Request, challenge: str = None):
    """
    Handle GET requests for webhook verification.
    Nylas sends: GET /webhooks/nylas?challenge=xxx
    """
    print("=" * 50)
    print(f"[{datetime.now()}] GET Webhook Verification")
    print(f"Challenge: {challenge}")
    print(f"Query params: {dict(request.query_params)}")
    print(f"Headers: {dict(request.headers)}")
    print("=" * 50)
    
    if challenge:
        # Return the challenge as PLAIN TEXT (not JSON)
        # This is what most webhook verification systems expect
        return Response(
            content=challenge,
            media_type="text/plain",
            headers={"Content-Type": "text/plain"}
        )
    
    # If no challenge, just return OK
    return Response(content="OK", media_type="text/plain")

@router.post("/webhooks/nylas")
async def nylas_webhook_post(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Handle POST requests for actual webhook events.
    """
    print("=" * 50)
    print(f"[{datetime.now()}] POST Webhook Event")
    print(f"Headers: {dict(request.headers)}")
    
    try:
        # Read the raw body first for logging
        body_bytes = await request.body()
        body_str = body_bytes.decode()
        print(f"Raw body: {body_str}")
        
        # Parse JSON
        payload = json.loads(body_str) if body_str else {}
        
        # Check if this is a POST challenge
        if "challenge" in payload:
            print(f"POST Challenge received: {payload['challenge']}")
            return Response(
                content=payload["challenge"],
                media_type="text/plain",
                headers={"Content-Type": "text/plain"}
            )
        
        # Handle actual webhook events
        print(f"Webhook Event Type: {payload.get('type', 'unknown')}")
        print(f"Full Event: {payload}")
        
        webhook_events.append(payload)

        
        # Keep only last 50 events
        if len(webhook_events) > 50:
            webhook_events.pop(0)
        
        # Process notetaker events
        event_type = payload.get("type", "")
        if "notetaker.media" in event_type:
            print(f"Processing notetaker media event: {event_type}")
            
            data = payload.get("data", {})
            object_data = data.get("object", {})

            # Get Nylas meeting ID from correct location
            nylas_meeting_id = object_data.get("id")
            meeting_name = object_data.get("name", "Unknown Meeting")
            
            print(f"📦 Nylas meeting ID: {nylas_meeting_id}")
            print(f"🏷️  Meeting name from Nylas: '{meeting_name}'")
            
            if not nylas_meeting_id:
                print(" No meeting ID found")
                return Response(content="OK", media_type="text/plain")
            
            # ========== FIND MEETING (MULTIPLE WAYS) ==========
            call = None
            
            # 1. Try by Nylas meeting_id (exact match)
            result = await db.execute(
                select(Call).filter(Call.meeting_id == nylas_meeting_id)
            )
            call = result.scalar_one_or_none()
            
            # 2. Try by title if not found (Nylas sometimes sends different IDs)
            if not call:
                print(f"🔍 No meeting found by Nylas ID, trying by title: '{meeting_name}'")
                result = await db.execute(
                    select(Call)
                    .filter(Call.title == meeting_name)
                    .order_by(Call.created_at.desc())
                )
                call = result.scalar_one_or_none()
            
            if not call:
                print(f"No meeting found for:")
                print(f"   Nylas ID: {nylas_meeting_id}")
                print(f"   Meeting name: '{meeting_name}'")
                print("Possible reasons:")
                print("   1. Schedule failed to save meeting_id")
                print("   2. This webhook is for a different meeting")
                print("   3. Database issue")
                return Response(content="OK", media_type="text/plain")
            
            print(f"✅ Found meeting: '{call.title}' (Your ID: {call.id})")
            
            # ========== CHECK IF ALREADY PROCESSED ==========
            if call.transcript and len(call.transcript) > 100:
                print(f"Already processed ({len(call.transcript)} chars), skipping")
                return Response(content="OK", media_type="text/plain")
            
            # ========== UPDATE MEETING ID IF NEEDED ==========
            if not call.meeting_id or call.meeting_id != nylas_meeting_id:
                call.meeting_id = nylas_meeting_id
                await db.commit()
                print(f"📝 Updated meeting with Nylas ID: {nylas_meeting_id}")
            
            # Get media URLs
            media = object_data.get("media", {})
            
            # Fetch and save transcript
            transcript_url = media.get("transcript")
            if transcript_url:
                try:
                    print(f"Fetching transcript...")
                    response = requests.get(transcript_url, timeout=10)
                    if response.status_code == 200:
                        transcript_data = response.json()
                        
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
                        
                        call.transcript = clean_transcript_text
                        print(f"Saved clean transcript: {len(clean_transcript_text)} chars")
                        
                        # ========== PROCESS FOR RAG ==========
                        try:
                            chunks_created = await rag_service.process_meeting_for_rag(
                                {
                                    "id": call.id,
                                    "tenant_id": call.tenant_id,
                                    "transcript": clean_transcript_text,
                                },
                                db
                            )
                            print(f"Created {chunks_created} RAG chunks with embeddings")
                        except Exception as e:
                            print(f"RAG processing failed: {e}")
                        # ========== END RAG PROCESSING ==========
                        
                except Exception as e:
                    print(f"Error fetching transcript: {e}")
            
            # Fetch summary
            summary_url = media.get("summary")
            if summary_url:
                try:
                    print(f"Fetching summary...")
                    response = requests.get(summary_url, timeout=10)
                    if response.status_code == 200:
                        summary_text = response.text
                        call.summary = summary_text[:5000] if len(summary_text) > 5000 else summary_text
                        print(f"Saved summary: {len(call.summary)} chars")
                except Exception as e:
                    print(f"Error fetching summary: {e}")
            
            # Fetch action items
            action_items_url = media.get("action_items")
            if action_items_url:
                try:
                    print(f"Fetching action items...")
                    response = requests.get(action_items_url, timeout=10)
                    if response.status_code == 200:
                        action_items_data = response.json()
                        call.action_items = action_items_data
                        print(f"Saved action items")
                except Exception as e:
                    print(f"Error fetching action items: {e}")
            
            # Save all changes
            await db.commit()
            print(f"Added transcript/summary to meeting: {call.title}")
            
            
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}")
        return Response(content="Invalid JSON", media_type="text/plain", status_code=400)
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return Response(content="Error", media_type="text/plain", status_code=500)
    
    print("=" * 50)
    
    return Response(content="OK", media_type="text/plain")
