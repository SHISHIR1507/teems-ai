from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..dependencies import get_db_session
from ..models.agent import Agent
from ..schemas.agent import AgentResponse, AgentListResponse, AgentListItem

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


