from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, text
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


def _tail_log(path: Path, lines: int = 80):
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
            {
                "id": partner.id,
                "investor_id": partner.investor_id,
                "name": partner.name,
                "role": partner.role,
                "linkedin_url": partner.linkedin_url,
                "twitter_url": partner.twitter_url,
                "source_url": None,
                "confidence": None,
                "updated_at": None,
            }
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
    query = apply_investor_filters(
        db.query(Investor),
        q=q,
        sector=sector,
        stage=stage,
        geography=geography,
    )

    investors = (
        query
        .order_by(Investor.updated_at.desc().nullslast(), Investor.firm.asc())
        .limit(limit)
        .all()
    )

    items = []

    for investor in investors:
        item = serialize_investor(investor)
        item.update(
            {
                "firm_name": investor.firm,
                "distance": 0.0,
                "semantic_score": 0.0,
                "hybrid_score": 0.0,
                "sector_boost": 0.0,
                "stage_boost": 0.0,
                "geography_boost": 0.0,
            }
        )
        items.append(item)

    return {
        "items": items,
        "total": len(items),
        "query": q,
    }


@router.get("/pipeline/status")
def pipeline_status():
    return {
        "pipeline_log": _tail_log(PROJECT_ROOT / "pipeline.log"),
        "scheduler_log": _tail_log(PROJECT_ROOT / "scheduler.log"),
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

    return {
        "queue": {
            "pending": pending,
            "completed": completed,
            "failed": failed,
            "total": pending + completed + failed,
        },
        "crawled_urls": db.query(CrawledUrl).count(),
        "failed_urls": db.query(FailedUrl).count(),
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
