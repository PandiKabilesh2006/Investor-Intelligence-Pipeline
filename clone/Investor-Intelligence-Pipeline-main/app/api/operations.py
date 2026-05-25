from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.api.schemas import (
    CrawlQueueItem,
    CrawledUrlItem,
    FailedUrlItem,
    OperationsMetrics,
)
from app.database.models import (
    CrawlQueue,
    CrawledUrl,
    FailedUrl,
    Investor,
    Partner,
    PipelineRun,
    PortfolioCompany,
)


router = APIRouter(prefix="/api/operations", tags=["operations"])


@router.get("/metrics", response_model=OperationsMetrics)
def get_metrics(db: Session = Depends(get_db)):
    last_pipeline_run = None

    try:
        run = (
            db.query(PipelineRun)
            .order_by(PipelineRun.started_at.desc().nullslast(), PipelineRun.id.desc())
            .first()
        )

        if run:
            last_pipeline_run = {
                "id": run.id,
                "status": run.status,
                "trigger": run.trigger,
                "started_at": run.started_at,
                "ended_at": run.ended_at,
            }
    except SQLAlchemyError:
        db.rollback()

    return {
        "total_investors": db.query(Investor).count(),
        "total_partners": db.query(Partner).count(),
        "total_portfolio_companies": db.query(PortfolioCompany).count(),
        "total_crawled_urls": db.query(CrawledUrl).count(),
        "total_failed_urls": db.query(FailedUrl).count(),
        "pending_failed_urls": (
            db.query(FailedUrl)
            .filter(FailedUrl.status == "pending")
            .count()
        ),
        "queue_depth": (
            db.query(CrawlQueue)
            .filter(CrawlQueue.status == "pending")
            .count()
        ),
        "last_investor_update": db.query(
            func.max(Investor.updated_at)
        ).scalar(),
        "last_pipeline_run": last_pipeline_run,
    }


@router.get("/crawl-queue", response_model=list[CrawlQueueItem])
def get_crawl_queue(
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(CrawlQueue)

    if status:
        query = query.filter(CrawlQueue.status == status)

    return (
        query
        .order_by(CrawlQueue.discovered_at.desc().nullslast())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/crawled-urls", response_model=list[CrawledUrlItem])
def get_crawled_urls(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return (
        db.query(CrawledUrl)
        .order_by(CrawledUrl.updated_at.desc().nullslast())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/failed-urls", response_model=list[FailedUrlItem])
def get_failed_urls(
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(FailedUrl)

    if status:
        query = query.filter(FailedUrl.status == status)

    return (
        query
        .order_by(FailedUrl.last_attempt.desc().nullslast())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.post(
    "/failed-urls/{failed_url_id}/retry",
    response_model=FailedUrlItem,
    dependencies=[Depends(require_admin)],
)
def mark_failed_url_for_retry(
    failed_url_id: int,
    db: Session = Depends(get_db),
):
    failed_url = (
        db.query(FailedUrl)
        .filter(FailedUrl.id == failed_url_id)
        .first()
    )

    if not failed_url:
        raise HTTPException(status_code=404, detail="Failed URL not found")

    failed_url.status = "pending"
    db.commit()
    db.refresh(failed_url)

    return failed_url
