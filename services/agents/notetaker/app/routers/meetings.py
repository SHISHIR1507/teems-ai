from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import requests
from app.core.database import get_db
from app.core.config import settings
from app.models.call import Call
from app.schemas.request import ChatRequest
from app.services.rag_service import rag_service

router = APIRouter()

@router.post("/schedule-notetaker")
def schedule_notetaker(payload: dict, db: Session = Depends(get_db)):

    meeting_link = payload.get("meeting_link")
    start_time = payload.get("start_time")
    title = "Teems.ai"  # ← ALWAYS THIS

    if not meeting_link or not start_time:
        raise HTTPException(status_code=400, detail="meeting_link and start_time are required")

    # Ensure start_time is valid ISO format
    try:
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid start_time format")

    if start_dt <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="start_time must be in the future")

    # ========== SAVE TO OUR DATABASE FIRST ==========
    call = Call(
        title=title,
        meeting_link=meeting_link,
        start_time=start_dt,  # Use parsed datetime
        created_at=datetime.utcnow()
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    
    print(f"Saved meeting to database: {call.id} - {title}")
    print(f" Meeting time: {start_dt}")
    
    # ========== NOW SCHEDULE WITH NYLAS ==========
    nylas_payload = {
        "meeting_link": meeting_link,
        "name": "Teems.ai",
        "start_time": start_time,  # Original string format
        "meeting_settings": {
            "transcription": True,
            "summary": True,
            "action_items": True,
            "audio_recording": True,
            "video_recording": True
        }
    }
    
    # DEBUG LOGGING
    print("=" * 60)
    print("DEBUG: Sending to Nylas API")
    import json
    print("Payload:", json.dumps(nylas_payload, indent=2))
    print("-" * 60)
    
    res = requests.post(
        f"{settings.NYLAS_BASE_URL}/v3/notetakers",
        headers={
            "Authorization": f"Bearer {settings.NYLAS_API_KEY}",
            "Content-Type": "application/json"
        },
        json=nylas_payload
    )
    
    # DEBUG LOGGING
    print(f"Response Status: {res.status_code}")
    print(f"Response Body: {res.text}")
    print("=" * 60)
    
    if res.status_code not in [200, 201, 202]:
        # Rollback our database entry if Nylas fails
        db.delete(call)
        db.commit()
        raise HTTPException(status_code=500, detail=res.json())
    
    # ========== SAVE NYLAS MEETING ID ==========
    try:
        nylas_response = res.json()
        nylas_meeting_id = nylas_response.get("data", {}).get("id")
        
        if nylas_meeting_id:
            call.meeting_id = nylas_meeting_id
            db.commit()
            print(f" Linked to Nylas meeting ID: {nylas_meeting_id}")
        else:
            print(f" No meeting ID in Nylas response")
    except Exception as e:
        print(f"⚠️ Failed to parse Nylas response: {e}")
    
    return {
        "success": True,
        "message": "Meeting scheduled and saved",
        "call_id": call.id,
        "meeting_saved": {
            "id": call.id,
            "title": call.title,
            "meeting_link": call.meeting_link,
            "start_time": call.start_time.isoformat() if call.start_time else None,
            "created_at": call.created_at.isoformat() if call.created_at else None
        },
        "nylas_response": res.json()
    }

@router.post("/meetings/{call_id}/chat")
async def chat_about_meeting(
    call_id: str,
    request: ChatRequest,  # ← Use Pydantic model
    db: Session = Depends(get_db)
):
    query = request.query.strip()
    
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")
    
    # Get meeting
    call = db.query(Call).filter(Call.id == call_id).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    if not call.transcript:
        raise HTTPException(status_code=400, detail="No transcript available")
        
    # Search relevant chunks
    relevant_chunks = await rag_service.search_relevant_chunks(query, call_id, db, top_k=5)
    
    if not relevant_chunks:
        return {
            "answer": "I couldn't find relevant information in the meeting notes for your question.",
            "meeting_title": call.title
        }
    
    answer = await rag_service.generate_answer(query, relevant_chunks, call.title)
    
    return {
        "answer": answer,
        "meeting_title": call.title,
        "chunks_used": len(relevant_chunks),
        "query": query
    }
