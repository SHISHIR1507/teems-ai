from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..dependencies import get_db_session
from ..models.agent import Agent, AgentRun, AgentAssignment
from ..schemas.agent import (
    AgentResponse,
    AgentListResponse,
    AgentListItem,
    AgentCreate,
    AgentUpdate,
    AgentRunRequest,
    AgentRunResponse,
    AgentAssignmentRequest,
    AgentAssignmentResponse,
)
from ..auth import require_tenant, AuthenticatedUser

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("/", response_model=AgentListResponse, summary="Get all agents")
async def get_agents(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    category: Optional[str] = Query(None, description="Filter by category"),
    db: AsyncSession = Depends(get_db_session),
):
    # Build query
    query = select(Agent)

    # Apply filters
    if category:
        query = query.where(Agent.category == category)

    # Get total count
    count_query = select(func.count()).select_from(Agent)
    if category:
        count_query = count_query.where(Agent.category == category)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Apply pagination
    offset = (page - 1) * size
    query = query.offset(offset).limit(size).order_by(Agent.created_at.desc())

    # Execute query
    result = await db.execute(query)
    agents = result.scalars().all()

    # Convert to response
    agent_items = [AgentListItem.from_orm(agent) for agent in agents]

    return AgentListResponse(
        agents=agent_items,
        total=total,
        page=page,
        size=size
    )

@router.post("/", response_model=AgentResponse, summary="Create a new agent")
async def create_agent(
    payload: AgentCreate,
    db: AsyncSession = Depends(get_db_session),
):
    agent = Agent(**payload.model_dump())
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return AgentResponse.from_orm(agent)


@router.get("/{agent_id}", response_model=AgentResponse, summary="Get agent by ID")
async def get_agent(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Get detailed information about a specific agent."""
    
    query = select(Agent).where(Agent.id == agent_id)
    result = await db.execute(query)
    agent = result.scalar_one_or_none()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return AgentResponse.from_orm(agent)


@router.put("/{agent_id}", response_model=AgentResponse, summary="Update an existing agent")
async def update_agent(
    agent_id: UUID,
    payload: AgentUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in updates.items():
        setattr(agent, field, value)

    await db.commit()
    await db.refresh(agent)
    return AgentResponse.from_orm(agent)


@router.post("/{agent_id}/run", response_model=AgentRunResponse, summary="Start agent execution")
async def run_agent(
    agent_id: UUID,
    payload: AgentRunRequest,
    user: AuthenticatedUser = Depends(require_tenant()),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    run = AgentRun(
        agent_id=agent.id,
        tenant_id=user.tenant_id,
        user_id=user.sub,
        status="queued",
        input_payload=payload.input_payload or {},
    )

    db.add(run)
    await db.commit()
    await db.refresh(run)
    return AgentRunResponse.from_orm(run)


@router.post("/{agent_id}/assign", response_model=AgentAssignmentResponse, summary="Assign agent to tenant/user")
async def assign_agent(
    agent_id: UUID,
    payload: AgentAssignmentRequest,
    user: AuthenticatedUser = Depends(require_tenant()),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    assignment = AgentAssignment(
        agent_id=agent.id,
        tenant_id=user.tenant_id,
        user_id=user.sub,
    )
    db.add(assignment)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        # Unique constraint to avoid duplicate assignment
        raise
    await db.refresh(assignment)
    return AgentAssignmentResponse.from_orm(assignment)

