from datetime import datetime, timezone
from pathlib import Path
import re
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
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
)


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


@router.get("/metrics")
def frontend_metrics(db: Session = Depends(get_db)):
    return {
        "investors": db.query(Investor).count(),
        "partners": db.query(Partner).count(),
        "portfolio_companies": db.query(PortfolioCompany).count(),
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

    if sector:
        query = query.filter(Investor.focus_sectors.any(sector))

    if stage:
        query = query.filter(Investor.investment_stage.any(stage))

    if geography:
        query = query.filter(Investor.geography.any(geography))

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
        sector_boost = 0.15 if sector and sector in (investor.focus_sectors or []) else 0.0
        stage_boost = 0.05 if stage and stage in (investor.investment_stage or []) else 0.0
        geography_boost = 0.10 if geography and geography in (investor.geography or []) else 0.0
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
