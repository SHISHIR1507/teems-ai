from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..clients import BrandfetchClient
from ..config import Settings, get_settings
from ..database import get_session
from ..models import BrandRecord
from ..schemas import BrandFetchRequest, BrandFetchResponse, BrandRecordResponse, BrandSummary

router = APIRouter(prefix="/brands", tags=["brands"])


async def get_brandfetch_client(settings: Settings = Depends(get_settings)) -> BrandfetchClient:
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
) -> BrandFetchResponse:
    domain = BrandfetchClient._extract_clean_domain(payload.url)

    existing = await session.scalar(select(BrandRecord).where(BrandRecord.domain == domain))
    if existing and not payload.force_refresh:
        return BrandFetchResponse(**map_record(existing).model_dump(), source="cache")

    data = await client.fetch(domain)

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

    return BrandFetchResponse(**map_record(existing).model_dump(), source="external")


@router.get(
    "/{domain}",
    response_model=BrandRecordResponse,
    summary="Lookup cached brand info; optionally refresh from Brandfetch",
)
async def get_brand(
    domain: str,
    refresh: bool = Query(default=False, description="Force refresh even if cached"),
    session: Annotated[AsyncSession, Depends(get_session)],
    client: Annotated[BrandfetchClient, Depends(get_brandfetch_client)],
) -> BrandRecordResponse:
    normalized = BrandfetchClient._extract_clean_domain(domain)
    record = await session.scalar(select(BrandRecord).where(BrandRecord.domain == normalized))

    if record and not refresh:
        return map_record(record)

    data = await client.fetch(normalized)

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


@router.get("/", response_model=list[BrandSummary], summary="List cached brand domains")
async def list_brands(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Annotated[AsyncSession, Depends(get_session)],
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

