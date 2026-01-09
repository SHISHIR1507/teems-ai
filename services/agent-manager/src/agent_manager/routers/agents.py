from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import AuthenticatedUser, require_tenant
from ..dependencies import get_db_session
from ..models.agent import Agent, AgentAssignment, AgentRun
from ..schemas.agent import (
    AgentAssignmentRequest,
    AgentAssignmentResponse,
    AgentCategoriesResponse,
    AgentCreate,
    AgentUpdate,
    AgentListItem,
    AgentListResponse,
    AgentResponse,
    AgentRunRequest,
    AgentRunResponse,
)

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("/categories", response_model=AgentCategoriesResponse, summary="Get all agent categories")
async def get_agent_categories(
    db: AsyncSession = Depends(get_db_session),
) -> AgentCategoriesResponse:
    """
    Return a list of distinct non-null agent categories.

    This is useful for populating filters or dropdowns on the frontend.
    """
    query = select(func.distinct(Agent.category)).where(Agent.category.isnot(None))
    result = await db.execute(query)
    categories = [row[0] for row in result.all() if row[0] is not None]
    return AgentCategoriesResponse(categories=categories)


@router.get("/", response_model=AgentListResponse, summary="Get all agents")
async def get_agents(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    category: Optional[str] = Query(None, description="Filter by category"),
    user: AuthenticatedUser = Depends(require_tenant()),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Return a paginated list of agents.

    Additionally, for the currently authenticated user, mark whether each agent
    is already assigned to this tenant/user so the frontend can render the
    proper state (e.g., "Added" vs "Add to workspace").
    """
    # Base query for agents (with optional category filter)
    query = select(Agent)
    if category:
        query = query.where(Agent.category == category)

    # Total count for pagination (respecting the same filter)
    count_query = select(func.count()).select_from(Agent)
    if category:
        count_query = count_query.where(Agent.category == category)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Apply pagination and ordering
    offset = (page - 1) * size
    query = query.offset(offset).limit(size).order_by(Agent.created_at.desc())

    # Execute main agent query
    result = await db.execute(query)
    agents: List[Agent] = result.scalars().all()

    # Fetch assignments for these agents for the current user/tenant
    assigned_agent_ids: set[UUID] = set()
    if agents:
        agent_ids = [agent.id for agent in agents]

        assignment_query = select(AgentAssignment.agent_id).where(
            and_(
                AgentAssignment.agent_id.in_(agent_ids),
                AgentAssignment.tenant_id == user.tenant_id,
                AgentAssignment.user_id == user.sub,
            )
        )
        assignment_result = await db.execute(assignment_query)
        assigned_agent_ids = {row[0] for row in assignment_result.all()}

    # Convert to response items, annotating assignment state
    agent_items: List[AgentListItem] = []
    for agent in agents:
        item = AgentListItem.from_orm(agent)
        # New field on the list item indicating assignment for this user.
        # The Pydantic model exposes this field; see AgentListItem in schemas/agent.py.
        item.is_assigned_to_current_user = agent.id in assigned_agent_ids  # type: ignore[attr-defined]
        agent_items.append(item)

    return AgentListResponse(
        agents=agent_items,
        total=total,
        page=page,
        size=size,
    )

@router.post("/", response_model=AgentResponse, summary="Create a new agent")
async def create_agent(
    payload: AgentCreate,
    db: AsyncSession = Depends(get_db_session),
):
    # Convert Pydantic models to dicts for JSON columns
    data = payload.model_dump()
    # work_samples needs to be converted from Pydantic models to dicts
    if "work_samples" in data and data["work_samples"]:
        data["work_samples"] = [item.model_dump() if hasattr(item, "model_dump") else item for item in data["work_samples"]]
    # tools_stack also needs conversion
    if "tools_stack" in data and data["tools_stack"]:
        data["tools_stack"] = [item.model_dump() if hasattr(item, "model_dump") else item for item in data["tools_stack"]]
    # works_well_with also needs conversion
    if "works_well_with" in data and data["works_well_with"]:
        data["works_well_with"] = [item.model_dump() if hasattr(item, "model_dump") else item for item in data["works_well_with"]]
    
    agent = Agent(**data)
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return AgentResponse.from_orm(agent)


@router.get("/{agent_id}", response_model=AgentResponse, summary="Get agent by ID")
async def get_agent(
    agent_id: UUID,
    user: AuthenticatedUser = Depends(require_tenant()),
    db: AsyncSession = Depends(get_db_session),
):
    """Get detailed information about a specific agent."""

    query = select(Agent).where(Agent.id == agent_id)
    result = await db.execute(query)
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Determine whether this agent is assigned to the current user in this tenant,
    # mirroring the semantics used in the list endpoint.
    assignment_query = select(AgentAssignment.agent_id).where(
        and_(
            AgentAssignment.agent_id == agent.id,
            AgentAssignment.tenant_id == user.tenant_id,
            AgentAssignment.user_id == user.sub,
        )
    )
    assignment_result = await db.execute(assignment_query)
    is_assigned = assignment_result.scalar_one_or_none() is not None

    response = AgentResponse.from_orm(agent)
    # Pydantic model exposes this field; see AgentResponse in schemas/agent.py.
    response.is_assigned_to_current_user = is_assigned  # type: ignore[attr-defined]
    return response


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
    # Convert Pydantic models to dicts for JSON columns
    if "work_samples" in updates and updates["work_samples"]:
        updates["work_samples"] = [item.model_dump() if hasattr(item, "model_dump") else item for item in updates["work_samples"]]
    if "tools_stack" in updates and updates["tools_stack"]:
        updates["tools_stack"] = [item.model_dump() if hasattr(item, "model_dump") else item for item in updates["tools_stack"]]
    if "works_well_with" in updates and updates["works_well_with"]:
        updates["works_well_with"] = [item.model_dump() if hasattr(item, "model_dump") else item for item in updates["works_well_with"]]
    
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

