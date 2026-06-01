import csv
import io
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Query,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db
from app.api.schemas import (
    InvestorDetail,
    InvestorListItem,
    InvestorListResponse,
)
from app.database.models import Investor, Partner, PortfolioCompany, ReviewQueue
from app.utils.normalization import (
    clean_list_values,
    expand_geography_filter,
    expand_sector_filter,
    normalize_geography,
    normalize_sector,
    normalize_stage,
)


router = APIRouter(prefix="/api/investors", tags=["investors"])


def _clean_list(value):
    return clean_list_values(value or [])


def _url_contains(url, domains):
    if not url:
        return False

    try:
        hostname = urlparse(url).hostname or ""
    except ValueError:
        return False

    hostname = hostname.lower()
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in domains)


def serialize_partner(partner):
    linkedin_url = partner.linkedin_url or None
    twitter_url = partner.twitter_url or None
    source_url = partner.source_url or None

    if linkedin_url and not _url_contains(linkedin_url, ["linkedin.com"]):
        source_url = source_url or linkedin_url
        linkedin_url = None

    if twitter_url and not _url_contains(twitter_url, ["twitter.com", "x.com"]):
        source_url = source_url or twitter_url
        twitter_url = None

    return {
        "id": partner.id,
        "name": partner.name,
        "role": partner.role,
        "title": partner.title,
        "linkedin_url": linkedin_url,
        "twitter_url": twitter_url,
        "source_url": source_url,
        "confidence": partner.extraction_confidence,
        "extraction_confidence": partner.extraction_confidence,
        "scraped_at": partner.scraped_at,
        "updated_at": partner.updated_at,
    }


def serialize_investor(investor):
    return {
        "id": investor.id,
        "firm": investor.firm,
        "website": investor.website,
        "source_url": investor.source_url,
        "focus_sectors": normalize_sector(investor.focus_sectors),
        "investment_stage": normalize_stage(investor.investment_stage),
        "geography": normalize_geography(investor.geography),
        "contact_links": _clean_list(investor.contact_links),
        "created_at": investor.created_at,
        "updated_at": investor.updated_at,
    }


def apply_investor_filters(query, q=None, sector=None, stage=None, geography=None):
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                Investor.firm.ilike(pattern),
                Investor.website.ilike(pattern),
                Investor.source_url.ilike(pattern),
            )
        )

    if sector:
        query = query.filter(
            or_(
                *[
                    Investor.focus_sectors.any(candidate)
                    for candidate in expand_sector_filter(sector)
                ]
            )
        )

    if stage:
        query = query.filter(Investor.investment_stage.any(stage))

    geography_candidates = expand_geography_filter(geography)

    if geography_candidates:
        query = query.filter(
            or_(
                *[
                    Investor.geography.any(candidate)
                    for candidate in geography_candidates
                ]
            )
        )

    return query


@router.get("", response_model=InvestorListResponse)
def list_investors(
    q: str | None = None,
    sector: str | None = None,
    stage: str | None = None,
    geography: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    base_query = apply_investor_filters(
        db.query(Investor),
        q=q,
        sector=sector,
        stage=stage,
        geography=geography,
    )

    total = base_query.count()

    investors = (
        base_query
        .order_by(Investor.updated_at.desc().nullslast(), Investor.firm.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "items": [
            serialize_investor(investor)
            for investor in investors
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/export")
def export_investors(
    q: str | None = None,
    sector: str | None = None,
    stage: str | None = None,
    geography: str | None = None,
    db: Session = Depends(get_db),
):
    investors = (
        apply_investor_filters(
            db.query(Investor),
            q=q,
            sector=sector,
            stage=stage,
            geography=geography,
        )
        .order_by(Investor.firm.asc())
        .all()
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "firm",
            "website",
            "source_url",
            "focus_sectors",
            "investment_stage",
            "geography",
            "contact_links",
            "created_at",
            "updated_at",
        ]
    )

    for investor in investors:
        writer.writerow(
            [
                investor.id,
                investor.firm,
                investor.website,
                investor.source_url,
                "; ".join(_clean_list(investor.focus_sectors)),
                "; ".join(_clean_list(investor.investment_stage)),
                "; ".join(_clean_list(investor.geography)),
                "; ".join(_clean_list(investor.contact_links)),
                investor.created_at,
                investor.updated_at,
            ]
        )

    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=investors.csv"
        },
    )


@router.get("/{investor_id}", response_model=InvestorDetail)
def get_investor(
    investor_id: int,
    db: Session = Depends(get_db),
):
    investor = (
        db.query(Investor)
        .options(
            selectinload(Investor.partners),
            selectinload(Investor.portfolio_companies),
        )
        .filter(Investor.id == investor_id)
        .first()
    )

    if not investor:
        raise HTTPException(status_code=404, detail="Investor not found")

    data = serialize_investor(investor)
    data["partners"] = [
        serialize_partner(partner)
        for partner in investor.partners or []
    ]
    data["portfolio_companies"] = investor.portfolio_companies or []

    return data


@router.patch("/{investor_id}", response_model=InvestorDetail)
def update_investor(
    investor_id: int,
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
):
    investor = (
        db.query(Investor)
        .options(
            selectinload(Investor.partners),
            selectinload(Investor.portfolio_companies),
        )
        .filter(Investor.id == investor_id)
        .first()
    )

    if not investor:
        raise HTTPException(status_code=404, detail="Investor not found")

    if "firm" in payload:
        firm = str(payload.get("firm") or "").strip()
        if not firm:
            raise HTTPException(status_code=422, detail="Firm name cannot be empty")
        investor.firm = firm

    for field in ["website", "source_url"]:
        if field in payload:
            setattr(investor, field, str(payload.get(field) or "").strip())

    if "focus_sectors" in payload:
        investor.focus_sectors = normalize_sector(payload.get("focus_sectors") or [])

    if "investment_stage" in payload:
        investor.investment_stage = normalize_stage(payload.get("investment_stage") or [])

    if "geography" in payload:
        investor.geography = normalize_geography(payload.get("geography") or [])

    if "contact_links" in payload:
        investor.contact_links = clean_list_values(payload.get("contact_links") or [])

    investor.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(investor)

    data = serialize_investor(investor)
    data["partners"] = [
        serialize_partner(partner)
        for partner in investor.partners or []
    ]
    data["portfolio_companies"] = investor.portfolio_companies or []
    return data


@router.delete("/{investor_id}")
def delete_investor(
    investor_id: int,
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
):
    investor = db.query(Investor).filter(Investor.id == investor_id).first()

    if not investor:
        raise HTTPException(status_code=404, detail="Investor not found")

    reason = str(payload.get("reason") or "Deleted from investor profile").strip()

    db.add(
        ReviewQueue(
            url=investor.source_url or investor.website,
            firm_name=investor.firm,
            source_text="Investor record manually deleted from the database.",
            extracted_payload={
                "firm": investor.firm,
                "website": investor.website,
                "source_url": investor.source_url,
                "focus_sectors": investor.focus_sectors or [],
                "investment_stage": investor.investment_stage or [],
                "geography": investor.geography or [],
                "contact_links": investor.contact_links or [],
            },
            ai_decision="manual_delete",
            ai_confidence=0.0,
            ai_reason=reason,
            status="rejected",
            human_label="rejected",
            human_reason=reason,
            reviewed_at=datetime.now(timezone.utc),
        )
    )

    db.query(Partner).filter(Partner.investor_id == investor.id).delete()
    db.query(PortfolioCompany).filter(PortfolioCompany.investor_id == investor.id).delete()
    db.delete(investor)
    db.commit()

    return {
        "deleted": True,
        "id": investor_id,
    }
