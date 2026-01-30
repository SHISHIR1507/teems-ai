from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request, Depends, Query
from fastapi import Request as FastAPIRequest
import json
import sys
from pathlib import Path
from datetime import datetime
from werkzeug.utils import secure_filename
from loguru import logger

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
    def resolve_conversation_id(v):
        import uuid as _u
        return v if (v and str(v).strip() and str(v).strip().lower() not in {"string", "optional-uuid", "uuid"}) else str(_u.uuid4())

from ..schemas.chat import ChatRequest, ChatResponse, ActionClickedRequest, ResetRequest
from ..schemas.document import DocumentResponse, DocumentUploadResponse
from ..dependencies import get_llm_host, get_all_tools, get_user_sessions, initialize_mcp_clients
from ..core.dependencies import get_db_session
from ..core import database as db_module
from ..core.config import get_settings
from ..core.auth import AuthenticatedUser, require_tenant
from ..services.rag.chunker import extract_text_from_file, chunk_text_token_based
from ..services.rag.vector_store import vector_store
from ..services.rag.s3_service import s3_service
from ..services.recommendation.engine import recommend_actions_and_agents
from ..services.db_helpers import (
    create_document,
    list_documents as list_documents_db,
    update_document_status,
    get_or_create_conversation,
    create_message,
    get_conversation_messages,
    get_conversation_by_session,
    delete_conversation
)
from ..services.realtime_notifier import (
    notify_chat_started,
    notify_chat_progress,
    notify_chat_completed,
    notify_chat_error,
    notify_document_processing,
    notify_tool_execution
)
from ..services.conversation_summarizer import summarize_conversation
from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter()
settings = get_settings()


@router.get("/health")
async def health():
    """
    Minimal health check endpoint.
    Returns ok if the service process is running.
    """
    return {
        "status": "ok",
        "service": "Eve Agent API",
        "version": "1.0.0",
    }


@router.get("/")
async def index():
    """API root endpoint"""
    return {
        "message": "Eve AI Server API",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc", 
            "health": "/health",
            "chat": "/api/chat",
            "upload": "/api/documents/upload",
            "documents": "/api/documents"
        },
        "description": "AI Assistant Backend API"
    }


@router.post("/api/chat", response_model=ChatResponse)
async def chat(
    chat_request: ChatRequest,
    request: FastAPIRequest,
    user: AuthenticatedUser = Depends(require_tenant()),
) -> ChatResponse:
    """Chat endpoint with REST response and realtime notifications via Redis"""
    user_message = chat_request.message.strip()
    session_id = resolve_conversation_id(chat_request.session_id)

    if not user_message:
        raise_standard_error(
            status_code=400,
            message="Empty message",
            detail="Message cannot be empty",
            field="message"
        )
    
    # Extract auth token from request headers
    auth_header = request.headers.get("authorization", "")
    auth_token = auth_header.replace("Bearer ", "").strip() if auth_header.startswith("Bearer ") else ""
    
    llm_host = get_llm_host()
    all_tools = get_all_tools()
    user_sessions = get_user_sessions()
    
    # Initialize database engine if needed
    db_module.init_engine()
    assert db_module.async_session_maker is not None
    # Get or create conversation in database
    async with db_module.async_session_maker() as db:
        conversation = await get_or_create_conversation(
            db, user.tenant_id, session_id, user.sub
        )
        await db.commit()
        conversation_id = conversation.id
    
    # Scope sessions by tenant to avoid cross-tenant collisions (for recent_actions and tools_used)
    internal_session_id = f"{user.tenant_id}:{session_id}"

    # Initialize in-memory session if not exists (for recent_actions and tools_used only)
    if internal_session_id not in user_sessions:
        user_sessions[internal_session_id] = {
            'recent_actions': [],
            'tools_used': []
        }
    
    # Notify chat started
    await notify_chat_started(user.tenant_id, session_id, user_message)
    
    try:
        # Notify initial progress
        await notify_chat_progress(
            user.tenant_id,
            session_id,
            {"step": "thinking", "progress": 10},
            "Thinking..."
        )
        
        # Track tools used in this conversation
        tools_used_in_turn = []
        
        # Call LLM
        response = llm_host.call_llm(user_message, tools=all_tools)
        result = llm_host.handle_response(response)
        
        # Handle tool calls
        max_iterations = 5
        iteration = 0
        
        while result["type"] == "tool_calls" and iteration < max_iterations:
            status_msg = f'Using tools... ({iteration + 1})'
            await notify_chat_progress(
                user.tenant_id,
                session_id,
                {"step": "tool_execution", "iteration": iteration + 1, "progress": 30 + (iteration * 10)},
                status_msg
            )
            iteration += 1
            
            # Track which tools were called
            for tool_call in result["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                tools_used_in_turn.append(tool_name)
                await notify_tool_execution(
                    user.tenant_id,
                    session_id,
                    tool_name,
                    "started",
                    {"iteration": iteration}
                )
            
            # Execute tools with tenant context from authenticated user
            llm_host.execute_tool_calls(result["tool_calls"], tenant_id=user.tenant_id)
            
            # Notify tool completion
            for tool_name in tools_used_in_turn[-len(result["tool_calls"]):]:
                await notify_tool_execution(
                    user.tenant_id,
                    session_id,
                    tool_name,
                    "completed",
                    {"iteration": iteration}
                )
            
            # Get next response
            response = llm_host.call_llm("", tools=all_tools)
            result = llm_host.handle_response(response)
        
        # Update session with tools used
        user_sessions[internal_session_id]['tools_used'].extend(tools_used_in_turn)
        
        # Process final response
        if result["type"] == "text":
            eve_reply = result['content']
            
            # Store messages in database
            async with db_module.async_session_maker() as db:
                await create_message(
                    db, conversation_id, user.tenant_id, "user", user_message, None, None
                )
                await create_message(
                    db, conversation_id, user.tenant_id, "assistant", eve_reply, 
                    {"tools_used": tools_used_in_turn} if tools_used_in_turn else None, 
                    None
                )
                await db.commit()
                
                # Retrieve recent messages for recommendations (last 10)
                recent_messages = await get_conversation_messages(
                    db, conversation_id, user.tenant_id, limit=10
                )
            
            # Format messages for recommendation context
            conversation_history = [
                {"role": msg.role, "content": msg.content}
                for msg in recent_messages
            ]
            
            # Generate recommendations based on context
            combined_context = f"{user_message} {eve_reply}"
            recent_actions = user_sessions[internal_session_id]['recent_actions']
            tools_used = user_sessions[internal_session_id]['tools_used']
            
            logger.info(f"\n🔍 Generating recommendations...")
            logger.info(f"   Domain detected from tools: {tools_used[-3:] if tools_used else 'none'}")
            logger.info(f"   Recent actions: {recent_actions[-3:] if recent_actions else 'none'}")
            
            # Use combined recommendations (actions + agents)
            recommendations = await recommend_actions_and_agents(
                query=combined_context,
                tenant_id=user.tenant_id,
                user_id=user.sub,
                auth_token=auth_token,
                recent_actions=recent_actions,
                tools_used=tools_used,
                k_actions=3,
                k_agents=2
            )
            logger.info(f"✓ Got {len(recommendations)} recommendations")
            
            # Convert recommendations to dict format with all fields
            rec_list = []
            for rec in recommendations:
                rec_dict = {
                    'action': rec.action,
                    'score': rec.score,
                    'id': rec.id,
                    'type': rec.type,
                    'click_action': rec.click_action or ("chat_followup" if rec.type == "action" else "navigate")
                }
                # Add agent-specific fields if present
                if rec.type == "agent":
                    if rec.agent_id:
                        rec_dict['agent_id'] = rec.agent_id
                    if rec.agent_manager_id:
                        rec_dict['agent_manager_id'] = rec.agent_manager_id
                    if rec.agent_name:
                        rec_dict['agent_name'] = rec.agent_name
                    if rec.is_assigned is not None:
                        rec_dict['is_assigned'] = rec.is_assigned
                    if rec.ui_route:
                        rec_dict['ui_route'] = rec.ui_route
                rec_list.append(rec_dict)
            
            logger.info(f"📤 Sending recommendations: {[r['action'] for r in rec_list]}")
            
            # Notify chat completed
            await notify_chat_completed(
                user.tenant_id,
                session_id,
                {
                    "response": eve_reply,
                    "recommendations": rec_list,
                    "tools_used": tools_used_in_turn
                }
            )
            
            # Return ChatResponse
            return ChatResponse(
                message=eve_reply,
                conversation_id=str(conversation_id),
                session_id=session_id,
                recommendations=rec_list,
                tools_used=tools_used_in_turn
            )
        else:
            error_msg = 'Max iterations reached'
            await notify_chat_error(user.tenant_id, session_id, error_msg)
            raise_standard_error(
                status_code=500,
                message="Max iterations reached",
                detail="Tool execution exceeded maximum iterations"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in chat: {e}")
        import traceback
        traceback.print_exc()
        error_msg = str(e)
        await notify_chat_error(user.tenant_id, session_id, error_msg, {"traceback": traceback.format_exc()})
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )


@router.post("/api/action_clicked")
async def action_clicked(
    action_request: ActionClickedRequest,
    request: FastAPIRequest,
    user: AuthenticatedUser = Depends(require_tenant()),
    db: AsyncSession = Depends(get_db_session),
):
    """Track when user clicks a recommendation button. For agents, generate conversation context."""
    action_id = action_request.action_id
    session_id = action_request.session_id
    
    # Extract auth token from request headers
    auth_header = request.headers.get("authorization", "")
    auth_token = auth_header.replace("Bearer ", "").strip() if auth_header.startswith("Bearer ") else ""
    
    user_sessions = get_user_sessions()
    
    internal_session_id = f"{user.tenant_id}:{session_id}"

    # Initialize in-memory session if not exists (for recent_actions and tools_used only)
    if internal_session_id not in user_sessions:
        user_sessions[internal_session_id] = {
            'recent_actions': [],
            'tools_used': []
        }
    
    # Check if this is an agent recommendation
    # Load agent specs to check if action_id matches an agent
    import sys
    from pathlib import Path
    agent_dir = Path(__file__).parent.parent.parent.parent / "agent"
    if str(agent_dir) not in sys.path:
        sys.path.insert(0, str(agent_dir))
    
    try:
        from resources.agent_loader import load_agent_spec
        from ..services.agent_manager_client import check_agent_assignment
        
        # Check if action_id matches any agent ID
        agent_spec = None
        try:
            agent_spec = load_agent_spec(action_id)
        except (FileNotFoundError, ImportError):
            # Not an agent, treat as regular action
            pass
        
        if agent_spec:
            # This is an agent recommendation
            agent_id = agent_spec.get('id')
            agent_name = agent_spec.get('name', agent_id)
            ui_route = agent_spec.get('ui_route', f'/agents/{agent_id}')
            agent_manager_id = agent_spec.get('agent_manager_id', '').strip()
            
            # Skip if agent_manager_id is placeholder
            if not agent_manager_id or agent_manager_id == '<uuid-from-agent-manager>':
                logger.warning(f"Agent {agent_id} has no valid agent_manager_id")
                agent_manager_id = None
            
            # Check if agent is assigned
            is_assigned = False
            assignment_error = None
            if agent_manager_id and auth_token:
                try:
                    is_assigned = await check_agent_assignment(
                        tenant_id=user.tenant_id,
                        user_id=user.sub,
                        agent_manager_id=agent_manager_id,
                        auth_token=auth_token
                    )
                except Exception as e:
                    logger.warning(f"Failed to check agent assignment: {e}")
                    assignment_error = str(e)
            
            # Get conversation from database
            conversation = await get_conversation_by_session(db, user.tenant_id, session_id)
            
            # Generate conversation context only if agent is assigned and we have conversation
            conversation_context = ""
            context_error = None
            if is_assigned and conversation:
                try:
                    # Get recent messages from database
                    recent_messages = await get_conversation_messages(
                        db, conversation.id, user.tenant_id, limit=10
                    )
                    if recent_messages:
                        # Format messages for summarizer
                        messages_list = [
                            {"role": msg.role, "content": msg.content}
                            for msg in recent_messages
                        ]
                        conversation_context = await summarize_conversation(
                            recent_messages=messages_list,
                            agent_name=agent_name
                        )
                except Exception as e:
                    logger.warning(f"Failed to generate conversation context: {e}")
                    context_error = str(e)
            
            # Track the click
            user_sessions[internal_session_id]['recent_actions'].append(action_id)
            user_sessions[internal_session_id]['recent_actions'] = user_sessions[internal_session_id]['recent_actions'][-10:]
            
            logger.info(f"📌 Agent recommendation clicked: {agent_id} (assigned: {is_assigned})")
            
            # Return response with agent metadata
            response = {
                "status": "tracked",
                "type": "agent",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "is_assigned": is_assigned,
                "ui_route": ui_route,
                "context_param": "eve_context"
            }
            
            if conversation_context:
                response["conversation_context"] = conversation_context
            
            if agent_manager_id:
                response["agent_manager_id"] = agent_manager_id
            
            # Include error details if any occurred
            if assignment_error:
                response["errors"] = response.get("errors", {})
                response["errors"]["agent_assignment_check"] = assignment_error
            
            if context_error:
                response["errors"] = response.get("errors", {})
                response["errors"]["conversation_context_generation"] = context_error
            
            return response
        else:
            # Regular action recommendation
            user_sessions[internal_session_id]['recent_actions'].append(action_id)
            user_sessions[internal_session_id]['recent_actions'] = user_sessions[internal_session_id]['recent_actions'][-10:]
            
            logger.info(f"📌 Action clicked: {action_id}")
            return {
                "status": "tracked",
                "type": "action"
            }
            
    except Exception as e:
        logger.warning(f"Error processing action click: {e}")
        import traceback
        traceback.print_exc()
        # Fallback to regular action tracking with error details
        user_sessions[internal_session_id]['recent_actions'].append(action_id)
        user_sessions[internal_session_id]['recent_actions'] = user_sessions[internal_session_id]['recent_actions'][-10:]
        return {
            "status": "tracked",
            "type": "action",
            "errors": {
                "processing": str(e)
            }
        }


@router.post("/api/reset")
async def reset(
    reset_request: ResetRequest,
    user: AuthenticatedUser = Depends(require_tenant()),
):
    """Reset conversation history"""
    session_id = reset_request.session_id
    
    # Reinitialize MCP clients and LLM
    initialize_mcp_clients()
    
    # Delete conversation from database (cascade deletes all messages)
    db = await get_db_session()
    conversation = await get_conversation_by_session(db, user.tenant_id, session_id)
    if conversation:
        await delete_conversation(db, conversation.id, user.tenant_id)
        await db.commit()
    
    # Reset in-memory session data (recent_actions and tools_used)
    user_sessions = get_user_sessions()
    internal_session_id = f"{user.tenant_id}:{session_id}"
    if internal_session_id in user_sessions:
        user_sessions[internal_session_id] = {
            'recent_actions': [],
            'tools_used': []
        }
    
    return {"status": "reset"}


@router.post("/api/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session),
):
    """Handle document upload and processing (S3 -> Extract -> Vector DB) with realtime notifications"""
    if not file.filename:
        raise_standard_error(
            status_code=400,
            message="No file selected",
            detail="Please select a file to upload",
            field="file"
        )

    # Enforce tenant_id from the authenticated user, not from the client
    tenant_id = user.tenant_id or ""
    session_id = f"doc_upload_{tenant_id}"  # Use a session ID for document uploads
    
    try:
        # Read file content
        file_content = await file.read()
        filename = secure_filename(file.filename)
        
        # 1. Upload to S3
        logger.info(f"📦 Step 1: Uploading to S3...")
        await notify_document_processing(
            tenant_id,
            session_id,
            "pending",
            "upload",
            {"filename": filename},
            "Uploading to S3..."
        )
        s3_url, s3_key = s3_service.upload_file(
            file_content=file_content,
            filename=filename,
            tenant_id=tenant_id,
            content_type=file.content_type or 'application/pdf'
        )
        logger.info(f"✅ Uploaded to S3: {s3_url}")

        # 2. Create Document Record
        logger.info(f"💾 Step 2: Creating document record...")
        await notify_document_processing(
            tenant_id,
            session_id,
            "pending",
            "create_record",
            {"filename": filename},
            "Creating document record..."
        )
        doc = await create_document(
            session=session,
            tenant_id=tenant_id,
            filename=filename,
            s3_url=s3_url,
            s3_key=s3_key,
            file_size_bytes=len(file_content),
            status="processing",
            metadata={"original_filename": file.filename}
        )
        logger.info(f"✅ Document created: {doc.id}")

        # 3. Extract Text & Chunk (Native Async)
        try:
            logger.info(f"📄 Step 3: Extracting text...")
            await notify_document_processing(
                tenant_id,
                session_id,
                str(doc.id),
                "extract",
                {"progress": 30},
                "Extracting text from document..."
            )
            text, metadata = await extract_text_from_file(file_content, filename)
            
            if not text or not text.strip():
                raise ValueError("No text could be extracted from the document.")

            logger.info(f"✅ Extracted {len(text)} characters")

            logger.info(f"✂️ Step 4: Chunking text...")
            await notify_document_processing(
                tenant_id,
                session_id,
                str(doc.id),
                "chunk",
                {"progress": 50, "text_length": len(text)},
                "Chunking text..."
            )
            chunks = chunk_text_token_based(
                text,
                chunk_tokens=settings.chunk_size,
                overlap_tokens=settings.chunk_overlap
            )
            logger.info(f"✅ Created {len(chunks)} chunks")

            logger.info(f"🧠 Step 5: Embedding & Storing...")
            await notify_document_processing(
                tenant_id,
                session_id,
                str(doc.id),
                "embed",
                {"progress": 70, "chunk_count": len(chunks)},
                "Generating embeddings and storing..."
            )
            await vector_store.store_chunks(
                db=session,
                document_id=doc.id,
                chunks=chunks,
                tenant_id=tenant_id
            )
            
            # Update document status
            await update_document_status(
                session=session,
                document_id=doc.id,
                tenant_id=tenant_id,
                status="completed",
                total_chunks=len(chunks),
                metadata=metadata
            )
            logger.info(f"✅ Processing complete!")
            
            await notify_document_processing(
                tenant_id,
                session_id,
                str(doc.id),
                "complete",
                {"progress": 100, "chunk_count": len(chunks)},
                "Document processing completed!"
            )
            
            return DocumentUploadResponse(
                message='Document uploaded and processed successfully',
                document_id=str(doc.id),
                s3_url=s3_url,
                processing_status="completed",
                total_chunks=len(chunks),
                chunks_processed=len(chunks)
            )
            
        except Exception as e:
            await update_document_status(
                session=session,
                document_id=doc.id,
                tenant_id=tenant_id,
                status="failed",
                metadata={"error": str(e)}
            )
            await notify_document_processing(
                tenant_id,
                session_id,
                str(doc.id),
                "error",
                {"error": str(e)},
                f"Document processing failed: {str(e)}"
            )
            raise e

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Processing failed: {e}")
        raise_standard_error(
            status_code=500,
            message="Internal server error",
            detail=str(e)
        )


@router.get("/api/documents")
async def list_documents(
    limit: int = 50,
    offset: int = 0,
    user: AuthenticatedUser = Depends(require_tenant()),
    session: AsyncSession = Depends(get_db_session),
):
    """List uploaded documents with pagination"""
    # Get tenant_id from authenticated user
    tenant_id = user.tenant_id or ""
    
    docs, total = await list_documents_db(session, tenant_id, limit=limit, offset=offset)
    
    return {
        "documents": [
            DocumentResponse(
                id=str(doc.id),
                filename=doc.filename,
                status=doc.status,
                s3_url=doc.s3_url,
                created_at=doc.created_at,
                total_chunks=doc.total_chunks
            )
            for doc in docs
        ],
        "total": total,
        "limit": limit,
        "offset": offset
    }
