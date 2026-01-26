"""
Session management router
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db_session
from app.core.auth import AuthenticatedUser, require_tenant
from app.models.schemas import SessionRequest, SessionResponse
from app.services.db_helpers import (
    get_or_create_session,
    get_session,
    delete_session,
    list_user_sessions
)
import uuid

router = APIRouter()


@router.post("/v1/sessions", response_model=SessionResponse, tags=["sessions"])
async def create_session(
    request: SessionRequest,
    user: AuthenticatedUser = Depends(require_tenant()),
    db: AsyncSession = Depends(get_db_session)
) -> SessionResponse:
    """
    Create a new fashion photo session.
    
    If conversation_id is provided, uses it; otherwise generates a new UUID.
    """
    try:
        session_id = request.conversation_id or str(uuid.uuid4())
        tenant_id = user.tenant_id
        
        fashion_session = await get_or_create_session(
            db, session_id, tenant_id, user.sub
        )
        
        return SessionResponse(
            id=fashion_session.id,
            tenant_id=fashion_session.tenant_id,
            user_id=fashion_session.user_id,
            stage=fashion_session.stage,
            metadata=fashion_session.metadata,
            created_at=fashion_session.created_at.isoformat(),
            updated_at=fashion_session.updated_at.isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/sessions/{session_id}", response_model=SessionResponse, tags=["sessions"])
async def get_session_endpoint(
    session_id: str,
    user: AuthenticatedUser = Depends(require_tenant()),
    db: AsyncSession = Depends(get_db_session)
) -> SessionResponse:
    """Get session details"""
    try:
        tenant_id = user.tenant_id
        fashion_session = await get_session(db, session_id, tenant_id)
        
        if not fashion_session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return SessionResponse(
            id=fashion_session.id,
            tenant_id=fashion_session.tenant_id,
            user_id=fashion_session.user_id,
            stage=fashion_session.stage,
            metadata=fashion_session.metadata,
            created_at=fashion_session.created_at.isoformat(),
            updated_at=fashion_session.updated_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/v1/sessions/{session_id}", tags=["sessions"])
async def delete_session_endpoint(
    session_id: str,
    user: AuthenticatedUser = Depends(require_tenant()),
    db: AsyncSession = Depends(get_db_session)
):
    """Delete a session and all associated data"""
    try:
        tenant_id = user.tenant_id
        deleted = await delete_session(db, session_id, tenant_id)
        
        if not deleted:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {"status": "success", "message": "Session deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/sessions", tags=["sessions"])
async def list_sessions(
    user: AuthenticatedUser = Depends(require_tenant()),
    db: AsyncSession = Depends(get_db_session),
    limit: int = 50,
    offset: int = 0
):
    """List user's sessions"""
    try:
        tenant_id = user.tenant_id
        sessions = await list_user_sessions(db, tenant_id, user.sub, limit, offset)
        
        return {
            "sessions": [
                {
                    "id": s.id,
                    "stage": s.stage,
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat()
                }
                for s in sessions
            ],
            "total": len(sessions),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
