import csv
import io
from urllib.parse import urlparse

from fastapi import (
    APIRouter,
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
from app.database.models import Investor


router = APIRouter(prefix="/api/investors", tags=["investors"])


def _clean_list(value):
    return value or []


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
        "focus_sectors": _clean_list(investor.focus_sectors),
        "investment_stage": _clean_list(investor.investment_stage),
        "geography": _clean_list(investor.geography),
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
        query = query.filter(Investor.focus_sectors.any(sector))

    if stage:
        query = query.filter(Investor.investment_stage.any(stage))

    if geography:
        query = query.filter(Investor.geography.any(geography))

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
