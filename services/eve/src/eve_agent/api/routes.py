from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
import json
from werkzeug.utils import secure_filename

from ..schemas.chat import ChatRequest, ActionClickedRequest, ResetRequest
from ..schemas.document import DocumentResponse, DocumentUploadResponse
from ..dependencies import get_llm_host, get_all_tools, get_user_sessions, initialize_mcp_clients
from ..database.session import SessionLocal
from ..models.document import Document
from ..services.rag.chunker import extract_text_from_file, chunk_text_token_based
from ..services.rag.vector_store import vector_store
from ..services.rag.s3_service import s3_service
from ..services.recommendation.engine import recommend_actions
from ..config import get_settings
from ..auth import AuthenticatedUser, require_tenant

router = APIRouter()
settings = get_settings()

# Templates setup (if you have a templates folder)
try:
    templates = Jinja2Templates(directory="templates")
except:
    templates = None


@router.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok"}


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main HTML page"""
    if templates:
        return templates.TemplateResponse("index.html", {"request": request})
    else:
        return HTMLResponse(content="<h1>Eve AI Server</h1><p>API is running. Use /docs for API documentation.</p>")


@router.post("/api/chat")
async def chat(
    chat_request: ChatRequest,
    user: AuthenticatedUser = Depends(require_tenant()),
):
    """Chat endpoint with SSE streaming"""
    user_message = chat_request.message.strip()
    session_id = chat_request.session_id
    
    if not user_message:
        raise HTTPException(status_code=400, detail="Empty message")
    
    llm_host = get_llm_host()
    all_tools = get_all_tools()
    user_sessions = get_user_sessions()
    
    # Scope sessions by tenant to avoid cross-tenant collisions
    internal_session_id = f"{user.tenant_id}:{session_id}"

    # Initialize session if not exists
    if internal_session_id not in user_sessions:
        user_sessions[internal_session_id] = {'recent_actions': [], 'tools_used': []}
    
    async def generate():
        try:
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'content': 'Thinking...'})}\n\n"
            
            # Track tools used in this conversation
            tools_used_in_turn = []
            
            # Call LLM
            response = llm_host.call_llm(user_message, tools=all_tools)
            result = llm_host.handle_response(response)
            
            # Handle tool calls
            max_iterations = 5
            iteration = 0
            
            while result["type"] == "tool_calls" and iteration < max_iterations:
                yield f"data: {json.dumps({'type': 'status', 'content': f'Using tools... ({iteration + 1})'})}\n\n"
                iteration += 1
                
                # Track which tools were called
                for tool_call in result["tool_calls"]:
                    tool_name = tool_call["function"]["name"]
                    tools_used_in_turn.append(tool_name)
                
                # Execute tools
                llm_host.execute_tool_calls(result["tool_calls"])
                
                # Get next response
                response = llm_host.call_llm("", tools=all_tools)
                result = llm_host.handle_response(response)
            
            # Update session with tools used
            user_sessions[internal_session_id]['tools_used'].extend(tools_used_in_turn)
            
            # Send final response with recommendations
            if result["type"] == "text":
                eve_reply = result['content']
                
                # Generate recommendations based on context
                combined_context = f"{user_message} {eve_reply}"
                recent_actions = user_sessions[internal_session_id]['recent_actions']
                tools_used = user_sessions[internal_session_id]['tools_used']
                
                print(f"\n🔍 Generating recommendations...")
                print(f"   Domain detected from tools: {tools_used[-3:] if tools_used else 'none'}")
                print(f"   Recent actions: {recent_actions[-3:] if recent_actions else 'none'}")
                
                recommendations = recommend_actions(
                    combined_context, 
                    recent_actions=recent_actions,
                    tools_used=tools_used,
                    k=3, 
                    threshold=0.20
                )
                print(f"✓ Got {len(recommendations)} recommendations")
                
                # Convert recommendations to dict format
                rec_list = [
                    {
                        'action': rec.action,
                        'score': rec.score,
                        'id': rec.id
                    }
                    for rec in recommendations
                ]
                
                print(f"📤 Sending recommendations: {[r['action'] for r in rec_list]}")
                
                # Send message with recommendations
                yield f"data: {json.dumps({'type': 'message', 'content': eve_reply, 'recommendations': rec_list})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'error', 'content': 'Max iterations reached'})}\n\n"
                
        except Exception as e:
            print(f"❌ Error in chat: {e}")
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/api/action_clicked")
async def action_clicked(
    action_request: ActionClickedRequest,
    user: AuthenticatedUser = Depends(require_tenant()),
):
    """Track when user clicks a recommendation button"""
    action_id = action_request.action_id
    session_id = action_request.session_id
    
    user_sessions = get_user_sessions()
    
    internal_session_id = f"{user.tenant_id}:{session_id}"

    if internal_session_id not in user_sessions:
        user_sessions[internal_session_id] = {'recent_actions': [], 'tools_used': []}
    
    # Add to recent actions
    user_sessions[internal_session_id]['recent_actions'].append(action_id)
    
    # Keep only last 10 actions
    user_sessions[internal_session_id]['recent_actions'] = user_sessions[internal_session_id]['recent_actions'][-10:]
    
    print(f"📌 Action clicked: {action_id}")
    return {"status": "tracked"}


@router.post("/api/reset")
async def reset(
    reset_request: ResetRequest,
    user: AuthenticatedUser = Depends(require_tenant()),
):
    """Reset conversation history"""
    session_id = reset_request.session_id
    
    # Reinitialize MCP clients and LLM
    initialize_mcp_clients()
    
    # Reset session
    user_sessions = get_user_sessions()
    internal_session_id = f"{user.tenant_id}:{session_id}"
    if internal_session_id in user_sessions:
        user_sessions[internal_session_id] = {'recent_actions': [], 'tools_used': []}
    
    return {"status": "reset"}


@router.post("/api/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    tenant_id: str = Form("default"),
    user: AuthenticatedUser = Depends(require_tenant()),
):
    """Handle document upload and processing (S3 -> Extract -> Vector DB)"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No selected file")

    # Enforce tenant_id from the authenticated user, not from the client
    tenant_id = user.tenant_id or ""
    
    try:
        # Read file content
        file_content = await file.read()
        filename = secure_filename(file.filename)
        
        # 1. Upload to S3
        print(f"📦 Step 1: Uploading to S3...")
        s3_url, s3_key = s3_service.upload_file(
            file_content=file_content,
            filename=filename,
            tenant_id=tenant_id,
            content_type=file.content_type or 'application/pdf'
        )
        print(f"✅ Uploaded to S3: {s3_url}")

        db = SessionLocal()
        try:
            # 2. Create Document Record
            print(f"💾 Step 2: Creating document record...")
            doc = Document(
                tenant_id=tenant_id,
                filename=filename,
                s3_url=s3_url,
                s3_key=s3_key,
                file_size_bytes=len(file_content),
                status="processing",
                doc_metadata={"original_filename": file.filename}
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            print(f"✅ Document created: {doc.id}")

            # 3. Extract Text & Chunk (Native Async)
            try:
                print(f"📄 Step 3: Extracting text...")
                text, metadata = await extract_text_from_file(file_content, filename)
                
                if not text or not text.strip():
                    raise ValueError("No text could be extracted from the document.")

                print(f"✅ Extracted {len(text)} characters")

                print(f"✂️ Step 4: Chunking text...")
                chunks = chunk_text_token_based(
                    text,
                    chunk_tokens=settings.chunk_size,
                    overlap_tokens=settings.chunk_overlap
                )
                print(f"✅ Created {len(chunks)} chunks")

                print(f"🧠 Step 5: Embedding & Storing...")
                await vector_store.store_chunks(
                    db=db,
                    document_id=doc.id,
                    chunks=chunks,
                    tenant_id=tenant_id
                )
                
                # Update document status
                doc.status = "completed"
                doc.total_chunks = len(chunks)
                doc.doc_metadata = metadata
                db.commit()
                print(f"✅ Processing complete!")
                
                return DocumentUploadResponse(
                    message='Document uploaded and processed successfully',
                    document_id=str(doc.id),
                    s3_url=s3_url
                )
                
            except Exception as e:
                doc.status = "failed"
                doc.doc_metadata = {"error": str(e)}
                db.commit()
                raise e

        except Exception as e:
            print(f"❌ Processing failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            db.close()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/documents", response_model=list[DocumentResponse])
async def list_documents(
    tenant_id: str = "default",
    user: AuthenticatedUser = Depends(require_tenant()),
):
    """List uploaded documents"""
    # Enforce tenant_id from the authenticated user, not from the client
    tenant_id = user.tenant_id or ""
    db = SessionLocal()
    try:
        docs = db.query(Document).filter(Document.tenant_id == tenant_id).order_by(Document.created_at.desc()).all()
        
        return [
            DocumentResponse(
                id=str(doc.id),
                filename=doc.filename,
                status=doc.status,
                s3_url=doc.s3_url,
                created_at=doc.created_at,
                total_chunks=doc.total_chunks
            )
            for doc in docs
        ]
    finally:
        db.close()
