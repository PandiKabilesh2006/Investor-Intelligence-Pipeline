from datetime import datetime, timezone
from pathlib import Path
import re
from urllib.parse import urlparse

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.investors import apply_investor_filters, serialize_investor
from app.database.models import (
    CrawlQueue,
    CrawledUrl,
    FailedUrl,
    Investor,
    Partner,
    PipelineRun,
    PortfolioCompany,
    ReviewQueue,
)
from app.config.taxonomy import taxonomy_options
from app.utils.normalization import (
    clean_list_values,
    expand_geography_filter,
    expand_sector_filter,
    normalize_sector,
    normalize_stage,
)
from app.review_feedback import mark_reviewed
from app.extraction.firecrawl_extract import extract_website
from app.parsing.gpt_parser import parse_investor
from insert_into_db import insert_investor_data


router = APIRouter(prefix="/api", tags=["frontend-compat"])

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _url_contains(url, domains):
    if not url:
        return False

    try:
        hostname = urlparse(url).hostname or ""
    except ValueError:
        return False

    hostname = hostname.lower()
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in domains)


def _serialize_partner_for_frontend(partner):
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
        "investor_id": partner.investor_id,
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


def _tail_log(path: Path, lines: int = 40):
    if not path.exists():
        return {
            "exists": False,
            "last_modified": None,
            "tail": [],
        }

    content = path.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()

    return {
        "exists": True,
        "last_modified": datetime.fromtimestamp(
            path.stat().st_mtime,
            timezone.utc,
        ).isoformat(),
        "tail": content[-lines:],
    }


@router.get("/config/options")
def config_options():
    return taxonomy_options()


@router.get("/metrics")
def frontend_metrics(db: Session = Depends(get_db)):
    return {
        "investors": db.query(Investor).count(),
        "partners": db.query(Partner).count(),
        "portfolio_companies": db.query(PortfolioCompany).count(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _primary_distribution(counts):
    return [
        {
            "name": name,
            "value": value,
        }
        for name, value in sorted(
            counts.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ]


def _primary_sector_label(values):
    cleaned = clean_list_values(values)

    if not cleaned:
        return "Other / Unspecified"

    label = cleaned[0]

    normalized = normalize_sector([label])

    if len(normalized) == 1:
        return normalized[0]

    return label


def _primary_stage_label(values):
    normalized = normalize_stage(values or [])
    return normalized[0] if normalized else "Other / Unspecified"


@router.get("/dashboard/distributions")
def dashboard_distributions(db: Session = Depends(get_db)):
    sector_counts = {}
    stage_counts = {}

    rows = (
        db.query(
            Investor.focus_sectors,
            Investor.investment_stage,
        )
        .all()
    )

    for focus_sectors, investment_stage in rows:
        sector = _primary_sector_label(focus_sectors)
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

        stage = _primary_stage_label(investment_stage)
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

    total = len(rows)
    sectors = _primary_distribution(sector_counts)
    stages = _primary_distribution(stage_counts)

    return {
        "sectors": sectors,
        "stages": stages,
        "total_investors": total,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/partners")
def list_partners(
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Partner)

    if q:
        query = query.filter(Partner.name.ilike(f"%{q}%"))

    total = query.count()

    partners = (
        query
        .order_by(Partner.name.asc().nullslast())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "items": [
            _serialize_partner_for_frontend(partner)
            for partner in partners
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/portfolio-companies")
def list_portfolio_companies(
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = (
        db.query(
            PortfolioCompany,
            Investor.firm.label("investor_firm"),
            Investor.website.label("investor_website"),
        )
        .join(Investor, PortfolioCompany.investor_id == Investor.id)
    )

    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                PortfolioCompany.company_name.ilike(pattern),
                PortfolioCompany.sector.ilike(pattern),
                Investor.firm.ilike(pattern),
            )
        )

    total = query.count()

    rows = (
        query
        .order_by(
            PortfolioCompany.company_name.asc().nullslast(),
            Investor.firm.asc().nullslast(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "items": [
            {
                "id": company.id,
                "investor_id": company.investor_id,
                "company_name": company.company_name,
                "sector": company.sector,
                "investor_firm": investor_firm,
                "investor_website": investor_website,
            }
            for company, investor_firm, investor_website in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def _serialize_review_item(item):
    return {
        "id": item.id,
        "url": item.url,
        "firm_name": item.firm_name,
        "source_text": item.source_text,
        "extracted_payload": item.extracted_payload or {},
        "ai_decision": item.ai_decision,
        "ai_confidence": item.ai_confidence,
        "ai_reason": item.ai_reason,
        "status": item.status,
        "human_label": item.human_label,
        "human_reason": item.human_reason,
        "reviewer_notes": item.reviewer_notes,
        "created_at": item.created_at,
        "reviewed_at": item.reviewed_at,
    }


def _payload_has_structured_fields(payload):
    if not isinstance(payload, dict):
        return False

    structured_fields = [
        "focus_sectors",
        "investment_stage",
        "partners",
        "portfolio_companies",
        "geography",
        "contact_links",
    ]

    return any(payload.get(field) for field in structured_fields)


def _payload_has_insertable_investor_evidence(payload):
    if not isinstance(payload, dict):
        return False

    firm = str(payload.get("firm", "") or "").strip()
    website = str(payload.get("website", "") or "").strip()
    source_url = str(payload.get("source_url", "") or "").strip()

    return bool(firm and (website or source_url) and _payload_has_structured_fields(payload))


def _looks_like_placeholder_payload(payload, review_item):
    if not isinstance(payload, dict):
        return True

    firm = str(payload.get("firm", "") or "").strip()
    review_title = str(review_item.firm_name or "").strip()

    if not firm:
        return True

    if review_title and firm.lower() == review_title.lower():
        return True

    if not _payload_has_structured_fields(payload):
        return True

    word_count = len(re.findall(r"[A-Za-z0-9]+", firm))
    punctuation_count = len(re.findall(r"[^A-Za-z0-9\s&.-]", firm))

    return word_count > 10 or punctuation_count > 2


def _reparse_review_item_payload(review_item, payload):
    url = review_item.url or payload.get("source_url") or payload.get("website")

    if not url:
        return payload

    markdown = extract_website(url)

    if not markdown:
        return payload

    parsed = parse_investor(markdown)

    if not parsed or not parsed.get("firm"):
        return payload

    parsed["source_url"] = parsed.get("source_url") or url
    parsed["website"] = parsed.get("website") or payload.get("website") or url
    return parsed


@router.get("/review-queue")
def list_review_queue(
    status: str | None = Query(default="pending"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(ReviewQueue)

    if status and status != "all":
        query = query.filter(ReviewQueue.status == status)

    total = query.count()
    items = (
        query
        .order_by(ReviewQueue.created_at.desc().nullslast(), ReviewQueue.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "items": [_serialize_review_item(item) for item in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/review-queue")
def create_review_item(
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
):
    item = ReviewQueue(
        url=payload.get("url", ""),
        firm_name=payload.get("firm_name", ""),
        source_text=payload.get("source_text", ""),
        extracted_payload=payload.get("extracted_payload", {}),
        ai_decision=payload.get("ai_decision", "needs_review"),
        ai_confidence=payload.get("ai_confidence", 0.0),
        ai_reason=payload.get("ai_reason", ""),
        status="pending",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_review_item(item)


@router.patch("/review-queue/{item_id}")
def edit_review_item(
    item_id: int,
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
):
    item = db.query(ReviewQueue).filter(ReviewQueue.id == item_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")

    for field in [
        "url",
        "firm_name",
        "source_text",
        "extracted_payload",
        "ai_decision",
        "ai_confidence",
        "ai_reason",
        "reviewer_notes",
    ]:
        if field in payload:
            setattr(item, field, payload[field])

    db.commit()
    db.refresh(item)
    return _serialize_review_item(item)


@router.post("/review-queue/{item_id}/approve")
def approve_review_item(
    item_id: int,
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
):
    item = db.query(ReviewQueue).filter(ReviewQueue.id == item_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")

    extracted_payload = payload.get("extracted_payload") or item.extracted_payload or {}

    if _looks_like_placeholder_payload(extracted_payload, item):
        extracted_payload = _reparse_review_item_payload(item, extracted_payload)

    if not _payload_has_insertable_investor_evidence(extracted_payload):
        raise HTTPException(
            status_code=422,
            detail=(
                "Approved item still lacks investor evidence after re-parse. "
                "Edit the extracted JSON with real investor fields or reject it."
            ),
        )

    if extracted_payload:
        insert_investor_data(extracted_payload)

    item.extracted_payload = extracted_payload
    mark_reviewed(
        item,
        label="approved",
        reason=payload.get("human_reason", ""),
        notes=payload.get("reviewer_notes", ""),
    )
    db.commit()
    db.refresh(item)

    return _serialize_review_item(item)


@router.post("/review-queue/{item_id}/reject")
def reject_review_item(
    item_id: int,
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
):
    item = db.query(ReviewQueue).filter(ReviewQueue.id == item_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")

    mark_reviewed(
        item,
        label="rejected",
        reason=payload.get("human_reason", ""),
        notes=payload.get("reviewer_notes", ""),
    )
    db.commit()
    db.refresh(item)

    return _serialize_review_item(item)


@router.get("/search")
def frontend_search(
    q: str,
    sector: str | None = None,
    stage: str | None = None,
    geography: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    terms = [
        term
        for term in re.findall(r"[a-z0-9]+", q.lower())
        if len(term) >= 2 and term not in {"vc", "vcs", "venture", "capital", "investor", "investors", "firm", "firms"}
    ]

    query = db.query(
        Investor.id,
        Investor.firm,
        Investor.website,
        Investor.source_url,
        Investor.focus_sectors,
        Investor.investment_stage,
        Investor.geography,
        Investor.contact_links,
        Investor.created_at,
        Investor.updated_at,
    )

    sector_candidates = expand_sector_filter(sector)

    if sector_candidates:
        query = query.filter(
            or_(
                *[
                    Investor.focus_sectors.any(candidate)
                    for candidate in sector_candidates
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

    investors = query.all()

    items = []
    synonyms = {
        "ai": ["ai", "artificial intelligence", "enterprise ai", "machine learning", "ml"],
        "saas": ["saas", "software", "b2b saas", "cloud"],
        "fintech": ["fintech", "financial", "payments", "banking"],
        "seed": ["seed", "pre-seed", "early stage"],
        "preseed": ["pre-seed", "pre seed"],
        "series": ["series a", "series b"],
        "growth": ["growth", "growth stage"],
        "india": ["india", "indian"],
        "us": ["united states", "usa", "us"],
        "usa": ["united states", "usa", "us"],
        "europe": ["europe", "european"],
    }

    for investor in investors:
        text_parts = [
            investor.firm or "",
            investor.website or "",
            " ".join(investor.focus_sectors or []),
            " ".join(investor.investment_stage or []),
            " ".join(investor.geography or []),
        ]
        haystack = " ".join(text_parts).lower()
        weighted_hits = 0.0

        for term in terms:
            candidates = synonyms.get(term, [term])
            if any(candidate in haystack for candidate in candidates):
                weighted_hits += 1.0

        semantic_score = weighted_hits / max(len(terms), 1)
        sector_boost = 0.15 if sector_candidates and any(
            candidate in (investor.focus_sectors or [])
            for candidate in sector_candidates
        ) else 0.0
        stage_boost = 0.05 if stage and stage in (investor.investment_stage or []) else 0.0
        geography_boost = 0.10 if geography_candidates and any(
            candidate in (investor.geography or [])
            for candidate in geography_candidates
        ) else 0.0
        hybrid_score = min(
            1.0,
            semantic_score + sector_boost + stage_boost + geography_boost,
        )

        if hybrid_score <= 0 and terms:
            continue

        item = serialize_investor(investor)
        item.update(
            {
                "firm_name": investor.firm,
                "distance": round(1.0 - semantic_score, 4),
                "semantic_score": round(semantic_score, 4),
                "hybrid_score": round(hybrid_score, 4),
                "sector_boost": sector_boost,
                "stage_boost": stage_boost,
                "geography_boost": geography_boost,
            }
        )
        items.append(item)

    items = sorted(
        items,
        key=lambda item: item["hybrid_score"],
        reverse=True,
    )[:limit]

    return {
        "items": items,
        "total": len(items),
        "query": q,
    }


@router.get("/pipeline/status")
def pipeline_status(db: Session = Depends(get_db)):
    latest_run = (
        db.query(PipelineRun)
        .order_by(
            PipelineRun.started_at.desc().nullslast(),
            PipelineRun.id.desc(),
        )
        .first()
    )

    return {
        "pipeline_log": _tail_log(PROJECT_ROOT / "pipeline.log"),
        "scheduler_log": _tail_log(PROJECT_ROOT / "scheduler.log"),
        "latest_run": (
            {
                "id": latest_run.id,
                "status": latest_run.status,
                "trigger": latest_run.trigger,
                "started_at": latest_run.started_at,
                "ended_at": latest_run.ended_at,
                "error_message": (
                    latest_run.error_message[:3000]
                    if latest_run.error_message
                    else None
                ),
            }
            if latest_run
            else None
        ),
    }


@router.get("/pipeline/queue-summary")
def pipeline_queue_summary(db: Session = Depends(get_db)):
    pending = (
        db.query(CrawlQueue)
        .filter(CrawlQueue.status == "pending")
        .count()
    )
    completed = (
        db.query(CrawlQueue)
        .filter(CrawlQueue.status == "completed")
        .count()
    )
    failed = (
        db.query(CrawlQueue)
        .filter(CrawlQueue.status == "failed")
        .count()
    )
    pending_urls = (
        db.query(CrawlQueue)
        .filter(CrawlQueue.status == "pending")
        .order_by(CrawlQueue.discovered_at.asc().nullslast())
        .limit(5)
        .all()
    )

    return {
        "queue": {
            "pending": pending,
            "completed": completed,
            "failed": failed,
            "total": pending + completed + failed,
        },
        "pending_urls": [
            {
                "id": item.id,
                "url": item.url,
                "discovered_at": item.discovered_at,
            }
            for item in pending_urls
        ],
        "crawled_urls": db.query(CrawledUrl).count(),
        "failed_urls": db.query(FailedUrl).count(),
    }


@router.post("/pipeline/queue/clear-pending")
def clear_pending_queue(db: Session = Depends(get_db)):
    pending = (
        db.query(CrawlQueue)
        .filter(CrawlQueue.status == "pending")
        .count()
    )

    (
        db.query(CrawlQueue)
        .filter(CrawlQueue.status == "pending")
        .update(
            {
                "status": "skipped",
                "last_crawled": datetime.now(timezone.utc),
            },
            synchronize_session=False,
        )
    )
    db.commit()

    return {
        "updated": pending,
        "status": "skipped",
    }


@router.get("/pipeline/active-jobs")
def active_pipeline_jobs(db: Session = Depends(get_db)):
    active_runs = (
        db.query(PipelineRun)
        .filter(PipelineRun.status.in_(["pending", "running"]))
        .all()
    )

    return {
        "active": bool(active_runs),
        "jobs": [
            {
                "pid": run.id
            }
            for run in active_runs
        ],
    }


@router.post("/pipeline/trigger")
def frontend_pipeline_trigger():
    raise HTTPException(
        status_code=403,
        detail=(
            "Pipeline trigger requires the protected "
            "POST /api/pipeline/runs endpoint."
        ),
    )
