from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..clients import BrandfetchClient, DomainParsingError
from ..config import Settings
from ..database import get_session
from ..dependencies import get_llm_service, get_publisher_dep, get_settings_dep
from ..events import EventPublisher
from ..models import BrandRecord
from ..schemas import (
    BrandFetchRequest,
    BrandFetchResponse,
    BrandRecordResponse,
    BrandSummary,
    BrandUpdateRequest,
)
from ..services.llm import LLMService
from ..auth import require_tenant, AuthenticatedUser

router = APIRouter(prefix="/brands", tags=["brands"])


async def get_brandfetch_client(settings: Settings = Depends(get_settings_dep)) -> BrandfetchClient:
    return BrandfetchClient(settings)


def map_record(record: BrandRecord) -> BrandRecordResponse:
    return BrandRecordResponse(
        domain=record.domain,
        website_url=record.website_url,
        name=record.name,
        description=record.description,
        icon=record.icon,
        contact_email=record.contact_email,
        contact_phone=record.contact_phone,
        contact_address=record.contact_address,
        instagram_url=record.instagram_url,
        youtube_url=record.youtube_url,
        facebook_url=record.facebook_url,
        industry=record.industry,
        language=record.language,
        region=record.region,
        tone_of_voice=record.tone_of_voice,
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
    llm_service: Annotated[LLMService | None, Depends(get_llm_service)],
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
        mapped = _extract_brand_fields(data)
        if not mapped.get("tone_of_voice"):
            mapped["tone_of_voice"] = await _infer_tone_of_voice(llm_service, mapped)
        if existing:
            existing.name = mapped["name"]
            existing.description = mapped["description"]
            existing.icon = mapped["icon"]
            existing.website_url = mapped["website_url"]
            existing.contact_email = mapped["contact_email"]
            existing.contact_phone = mapped["contact_phone"]
            existing.contact_address = mapped["contact_address"]
            existing.instagram_url = mapped["instagram_url"]
            existing.youtube_url = mapped["youtube_url"]
            existing.facebook_url = mapped["facebook_url"]
            existing.industry = mapped["industry"]
            existing.language = mapped["language"]
            existing.region = mapped["region"]
            existing.tone_of_voice = mapped["tone_of_voice"]
            existing.raw = data
        else:
            existing = BrandRecord(
                domain=domain,
                name=mapped["name"],
                description=mapped["description"],
                icon=mapped["icon"],
                website_url=mapped["website_url"],
                contact_email=mapped["contact_email"],
                contact_phone=mapped["contact_phone"],
                contact_address=mapped["contact_address"],
                instagram_url=mapped["instagram_url"],
                youtube_url=mapped["youtube_url"],
                facebook_url=mapped["facebook_url"],
                industry=mapped["industry"],
                language=mapped["language"],
                region=mapped["region"],
                tone_of_voice=mapped["tone_of_voice"],
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
    llm_service: Annotated[LLMService | None, Depends(get_llm_service)],
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
        mapped = _extract_brand_fields(data)
        if not mapped.get("tone_of_voice"):
            mapped["tone_of_voice"] = await _infer_tone_of_voice(llm_service, mapped)
        if record:
            record.name = mapped["name"]
            record.description = mapped["description"]
            record.icon = mapped["icon"]
            record.website_url = mapped["website_url"]
            record.contact_email = mapped["contact_email"]
            record.contact_phone = mapped["contact_phone"]
            record.contact_address = mapped["contact_address"]
            record.instagram_url = mapped["instagram_url"]
            record.youtube_url = mapped["youtube_url"]
            record.facebook_url = mapped["facebook_url"]
            record.industry = mapped["industry"]
            record.language = mapped["language"]
            record.region = mapped["region"]
            record.tone_of_voice = mapped["tone_of_voice"]
            record.raw = data
        else:
            record = BrandRecord(
                domain=normalized,
                name=mapped["name"],
                description=mapped["description"],
                icon=mapped["icon"],
                website_url=mapped["website_url"],
                contact_email=mapped["contact_email"],
                contact_phone=mapped["contact_phone"],
                contact_address=mapped["contact_address"],
                instagram_url=mapped["instagram_url"],
                youtube_url=mapped["youtube_url"],
                facebook_url=mapped["facebook_url"],
                industry=mapped["industry"],
                language=mapped["language"],
                region=mapped["region"],
                tone_of_voice=mapped["tone_of_voice"],
                raw=data,
            )
            session.add(record)

        await session.commit()
        await session.refresh(record)
        return map_record(record)
    except Exception:
        await session.rollback()
        raise


@router.patch(
    "/{domain}",
    response_model=BrandRecordResponse,
    summary="Update stored brand metadata fields manually",
)
async def update_brand(
    domain: str,
    payload: BrandUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: AuthenticatedUser = Depends(require_tenant()),
) -> BrandRecordResponse:
    try:
        normalized = BrandfetchClient._extract_clean_domain(domain)
    except DomainParsingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    record = await session.scalar(select(BrandRecord).where(BrandRecord.domain == normalized))
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No cached record for '{normalized}'",
        )

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return map_record(record)

    # Apply only provided fields
    for key, value in updates.items():
        if hasattr(record, key):
            setattr(record, key, value)

    try:
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
            website_url=record.website_url,
            name=record.name,
            icon=record.icon,
            description=record.description,
            contact_email=record.contact_email,
            contact_phone=record.contact_phone,
            contact_address=record.contact_address,
            instagram_url=record.instagram_url,
            youtube_url=record.youtube_url,
            facebook_url=record.facebook_url,
            industry=record.industry,
            language=record.language,
            region=record.region,
            tone_of_voice=record.tone_of_voice,
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


def _first_or_none(iterable):
    return next((item for item in iterable if item), None)


def _extract_brand_fields(data: dict[str, Any]) -> dict[str, Any]:
    links = data.get("links") or []

    def link_for(name: str) -> str | None:
        name_lower = name.lower()
        for link in links:
            if (link.get("name") or "").lower() == name_lower:
                return link.get("url")
        return None

    company = data.get("company") or {}
    industries = company.get("industries") or []
    location = company.get("location") or {}

    address_parts = [
        location.get("city"),
        location.get("state"),
        location.get("country"),
    ]

    contact_email = _first_or_none(company.get("emails") or data.get("emails") or [])
    contact_phone = _first_or_none(company.get("phoneNumbers") or data.get("phoneNumbers") or [])

    return {
        "name": data.get("name"),
        "description": data.get("description"),
        "icon": data.get("icon"),
        "website_url": f"https://{data['domain']}" if data.get("domain") else None,
        "contact_email": contact_email,
        "contact_phone": contact_phone,
        "contact_address": ", ".join([part for part in address_parts if part]).strip(", ") or None,
        "instagram_url": link_for("instagram"),
        "youtube_url": link_for("youtube"),
        "facebook_url": link_for("facebook"),
        "industry": industries[0].get("name") if industries else None,
        "language": company.get("language") or data.get("language"),
        "region": location.get("region") or location.get("country") or location.get("countryCode"),
        "tone_of_voice": company.get("toneOfVoice") or data.get("toneOfVoice"),
    }


async def _infer_tone_of_voice(llm_service: LLMService | None, mapped: dict[str, Any]) -> str | None:
    # If no LLM configured, skip gracefully
    if llm_service is None:
        return None

    parts = []
    for key in ["name", "description", "industry", "language", "region"]:
        val = mapped.get(key)
        if val:
            parts.append(f"{key.title()}: {val}")
    for key in ["instagram_url", "youtube_url", "facebook_url", "website_url"]:
        val = mapped.get(key)
        if val:
            parts.append(f"{key.replace('_url', '').title()}: {val}")

    if not parts:
        return None

    messages = [
        {
            "role": "system",
            "content": (
                "You are a branding assistant. Given brand metadata (name, description, "
                "industry, region, language, and links), infer a concise tone-of-voice "
                "description for the brand.\n\n"
                "Format your answer as three comma-separated adjectives.\n\n"
                "Here are example tones of voice for reference:\n"
                "- Teems.ai — Friendly, confident, and innovative\n"
                "- Apple — Minimal, premium, and precise\n"
                "- Nike — Bold, motivational, and energetic\n"
                "- IKEA — Friendly, practical, and witty\n"
                "- Airbnb — Warm, welcoming, and story-driven\n"
                "- Google — Helpful, clear, and approachable\n"
                "- Spotify — Playful, modern, and expressive\n"
                "- Amazon — Efficient, direct, and customer-first\n"
                "- Tesla — Visionary, bold, and disruptive\n"
                "- Emirates — Polished, luxurious, and reassuring\n"
                "- Careem — Local, friendly, and convenient\n"
                "- Netflix — Playful, confident, and conversational\n\n"
                "Only output the three-adjective tone-of-voice phrase, under 12 words."
            ),
        },
        {"role": "user", "content": "\n".join(parts)},
    ]

    try:
        text = await llm_service.generate(messages, temperature=0.4)
    except Exception:
        return None

    return (text or "").strip()[:200] or None

