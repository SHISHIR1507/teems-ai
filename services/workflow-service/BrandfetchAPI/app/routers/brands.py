from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..clients import BrandfetchClient, DomainParsingError
from ..config import Settings
from ..database import get_session
from ..dependencies import (
    get_publisher_dep,
    get_settings_dep,
)
from ..events import EventPublisher
from ..models import BrandRecord
from ..schemas import BrandFetchRequest, BrandFetchResponse, BrandRecordResponse, BrandSummary
from ..auth import require_tenant, AuthenticatedUser

router = APIRouter(prefix="/brands", tags=["brands"])


async def get_brandfetch_client(settings: Settings = Depends(get_settings_dep)) -> BrandfetchClient:
    return BrandfetchClient(settings)


def map_record(record: BrandRecord) -> BrandRecordResponse:
    return BrandRecordResponse(
        domain=record.domain,
        name=record.name,
        description=record.description,
        icon=record.icon,
        details=record.raw,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.post("/fetch", response_model=BrandFetchResponse, summary="Fetch from Brandfetch and cache result")
async def fetch_brand(
    payload: BrandFetchRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    client: Annotated[BrandfetchClient, Depends(get_brandfetch_client)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    publisher: Annotated[EventPublisher, Depends(get_publisher_dep)],
    user: AuthenticatedUser = Depends(require_tenant()),
    request: Request = None,
) -> BrandFetchResponse:
    try:
        domain = BrandfetchClient._extract_clean_domain(payload.url)
    except DomainParsingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    existing = await session.scalar(select(BrandRecord).where(BrandRecord.domain == domain))
    if existing and not payload.force_refresh:
        response = BrandFetchResponse(**map_record(existing).model_dump(), source="cache")
        await _publish_onboarding_event(
            publisher,
            settings,
            user,
            _extract_conversation_id(payload, request),
            response,
        )
        return response

    try:
        data = await client.fetch(payload.url)
    except Exception:
        await session.rollback()
        raise

    try:
        if existing:
            existing.name = data.get("name")
            existing.description = data.get("description")
            existing.icon = data.get("icon")
            existing.raw = data
        else:
            existing = BrandRecord(
                domain=domain,
                name=data.get("name"),
                description=data.get("description"),
                icon=data.get("icon"),
                raw=data,
            )
            session.add(existing)

        await session.commit()
        await session.refresh(existing)

        response = BrandFetchResponse(**map_record(existing).model_dump(), source="external")
        await _publish_onboarding_event(
            publisher,
            settings,
            user,
            _extract_conversation_id(payload, request),
            response,
        )
        return response
    except Exception:
        await session.rollback()
        raise


@router.get(
    "/{domain}",
    response_model=BrandRecordResponse,
    summary="Lookup cached brand info; optionally refresh from Brandfetch",
)
async def get_brand(
    domain: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    client: Annotated[BrandfetchClient, Depends(get_brandfetch_client)],
    refresh: bool = Query(default=False, description="Force refresh even if cached"),
) -> BrandRecordResponse:
    try:
        normalized = BrandfetchClient._extract_clean_domain(domain)
    except DomainParsingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    record = await session.scalar(select(BrandRecord).where(BrandRecord.domain == normalized))

    if record and not refresh:
        return map_record(record)

    try:
        data = await client.fetch(domain)
    except Exception:
        await session.rollback()
        raise

    try:
        if record:
            record.name = data.get("name")
            record.description = data.get("description")
            record.icon = data.get("icon")
            record.raw = data
        else:
            record = BrandRecord(
                domain=normalized,
                name=data.get("name"),
                description=data.get("description"),
                icon=data.get("icon"),
                raw=data,
            )
            session.add(record)

        await session.commit()
        await session.refresh(record)
        return map_record(record)
    except Exception:
        await session.rollback()
        raise


@router.get("/", response_model=list[BrandSummary], summary="List cached brand domains")
async def list_brands(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[BrandSummary]:
    stmt = (
        select(BrandRecord)
        .order_by(BrandRecord.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    results = (await session.scalars(stmt)).all()
    return [
        BrandSummary(
            domain=record.domain,
            name=record.name,
            icon=record.icon,
            description=record.description,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
        for record in results
    ]


async def _publish_onboarding_event(
    publisher: EventPublisher,
    settings: Settings,
    user: AuthenticatedUser,
    conversation_id: str | None,
    response: BrandFetchResponse,
) -> None:
    if not user.tenant_id:
        return

    channel = f"{settings.onboarding_channel_prefix}:{user.tenant_id}"
    await publisher.publish(
        channel,
        {
            "type": "brandfetch.completed",
            "step": "get_company_details",
            "next_step": "add_agents",
            "tenant_id": user.tenant_id,
            "conversation_id": conversation_id,
            "domain": response.domain,
            "name": response.name,
            "description": response.description,
            "icon": response.icon,
            "source": response.source,
        },
    )


def _extract_conversation_id(payload: BrandFetchRequest, request: Request | None) -> str | None:
    # Prefer a header (e.g., set by gateway) and fall back to payload
    if request:
        header_val = request.headers.get("X-Conversation-Id") or request.headers.get("X-Conversation-ID")
        if header_val:
            return header_val
    return payload.conversation_id

