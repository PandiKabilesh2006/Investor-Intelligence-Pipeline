from datetime import datetime, timezone
from pathlib import Path
import json
import re
import subprocess
import sys
from urllib.parse import urlparse

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session, selectinload

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
from app.review_feedback import enqueue_review_item, mark_reviewed
from app.extraction.firecrawl_extract import (
    extract_manual_review_url_with_reason,
)
from app.parsing.gpt_parser import parse_investor
from app.utils.failed_url_manager import mark_url_blocked
from audit_investor_coverage import audit_investor_coverage
from build_enrichment_backlog import build_backlog
from enrich_investor_backlog import enrich_from_backlog
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


def _hostname(url):
    if not url:
        return ""

    try:
        return (urlparse(url).hostname or "").lower().replace("www.", "")
    except ValueError:
        return ""


def _host_matches_url(host, url):
    url_host = _hostname(url)
    return bool(url_host and (url_host == host or url_host.endswith(f".{host}")))


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


def _read_json_file(path: Path):
    if not path.exists():
        return {
            "exists": False,
            "last_modified": None,
            "summary": {},
            "items": [],
            "path": str(path),
        }

    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("records") or payload.get("backlog") or payload.get("results") or []

    return {
        "exists": True,
        "last_modified": datetime.fromtimestamp(
            path.stat().st_mtime,
            timezone.utc,
        ).isoformat(),
        "summary": payload.get("summary", {}),
        "items": items[:100],
        "total_items": len(items),
        "path": str(path),
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


def _investor_quality(investor):
    checks = {
        "website": bool(investor.website),
        "focus_sectors": bool(clean_list_values(investor.focus_sectors or [])),
        "investment_stage": bool(clean_list_values(investor.investment_stage or [])),
        "geography": bool(clean_list_values(investor.geography or [])),
        "contact_links": bool(clean_list_values(investor.contact_links or [])),
        "partners": bool(investor.partners),
        "portfolio_companies": bool(investor.portfolio_companies),
    }
    score = sum(1 for value in checks.values() if value)

    if score >= 6:
        status = "strong"
    elif score >= 4:
        status = "usable"
    else:
        status = "thin"

    return {
        "score": score,
        "max_score": len(checks),
        "status": status,
        "missing_fields": [
            field
            for field, present in checks.items()
            if not present
        ],
    }


@router.get("/quality/coverage")
def quality_coverage(db: Session = Depends(get_db)):
    investors = (
        db.query(Investor)
        .options(
            selectinload(Investor.partners),
            selectinload(Investor.portfolio_companies),
        )
        .all()
    )

    status_counts = {
        "strong": 0,
        "usable": 0,
        "thin": 0,
    }
    missing_counts = {}
    items = []

    for investor in investors:
        quality = _investor_quality(investor)
        status_counts[quality["status"]] += 1

        for field in quality["missing_fields"]:
            missing_counts[field] = missing_counts.get(field, 0) + 1

        items.append(
            {
                "id": investor.id,
                "firm": investor.firm,
                "website": investor.website,
                "updated_at": investor.updated_at,
                **quality,
            }
        )

    items.sort(key=lambda item: (item["score"], (item["firm"] or "").lower()))

    return {
        "total": len(investors),
        "status_counts": status_counts,
        "missing_counts": [
            {
                "name": name,
                "value": value,
            }
            for name, value in sorted(
                missing_counts.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        ],
        "items": items[:100],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/quality/bulk-delete")
def bulk_delete_quality_records(
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
):
    ids = payload.get("ids") or []
    reason = payload.get("reason") or "Bulk deleted from Data Quality."

    if not ids:
        raise HTTPException(status_code=422, detail="No investor ids provided")

    deleted = 0

    for investor in db.query(Investor).filter(Investor.id.in_(ids)).all():
        db.add(ReviewQueue(
            url=investor.source_url or investor.website or "",
            firm_name=investor.firm,
            source_text="Investor record bulk deleted from Data Quality.",
            extracted_payload={
                "firm": investor.firm,
                "website": investor.website,
                "source_url": investor.source_url,
                "_deleted_investor_id": investor.id,
            },
            ai_decision="bulk_delete",
            ai_confidence=1.0,
            ai_reason=reason,
            status="rejected",
            human_label="rejected",
            human_reason=reason,
            reviewed_at=datetime.now(timezone.utc),
        ))
        db.query(Partner).filter(Partner.investor_id == investor.id).delete()
        db.query(PortfolioCompany).filter(PortfolioCompany.investor_id == investor.id).delete()
        db.delete(investor)
        deleted += 1

    db.commit()
    return {"deleted": deleted}


@router.post("/quality/rebuild-backlog")
def rebuild_quality_backlog():
    audit_path = PROJECT_ROOT / "exports" / "investor_coverage_audit.json"
    backlog_path = PROJECT_ROOT / "exports" / "investor_enrichment_backlog.json"

    audit_investor_coverage(audit_path)
    build_backlog(audit_path, backlog_path)

    payload = json.loads(backlog_path.read_text(encoding="utf-8"))
    return payload.get("summary", {})


@router.get("/enrichment/audit")
def get_enrichment_audit():
    audit_path = PROJECT_ROOT / "exports" / "investor_coverage_audit.json"
    return _read_json_file(audit_path)


@router.post("/enrichment/audit")
def run_enrichment_audit():
    audit_path = PROJECT_ROOT / "exports" / "investor_coverage_audit.json"
    audit_investor_coverage(audit_path)
    return _read_json_file(audit_path)


@router.get("/enrichment/backlog")
def get_enrichment_backlog():
    backlog_path = PROJECT_ROOT / "exports" / "investor_enrichment_backlog.json"
    return _read_json_file(backlog_path)


@router.post("/enrichment/backlog")
def run_enrichment_backlog(payload: dict = Body(default={})):
    audit_path = PROJECT_ROOT / "exports" / "investor_coverage_audit.json"
    backlog_path = PROJECT_ROOT / "exports" / "investor_enrichment_backlog.json"

    if not audit_path.exists():
        audit_investor_coverage(audit_path)

    raw_limit = payload.get("limit")
    limit = None
    if raw_limit not in (None, ""):
        limit = max(1, min(int(raw_limit), 500))

    raw_min_score = payload.get("min_score", 6)
    min_score = max(1, min(int(raw_min_score), 7))

    build_backlog(
        audit_path=audit_path,
        output_path=backlog_path,
        min_score=min_score,
        limit=limit,
    )
    return _read_json_file(backlog_path)


@router.post("/enrichment/run")
def run_enrichment_batch(payload: dict = Body(default={})):
    backlog_path = PROJECT_ROOT / "exports" / "investor_enrichment_backlog.json"

    if not backlog_path.exists():
        raise HTTPException(
            status_code=409,
            detail="Build the enrichment backlog before running a batch.",
        )

    raw_limit = payload.get("limit", 10)
    limit = max(1, min(int(raw_limit), 50))
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = PROJECT_ROOT / "exports" / f"investor_enrichment_results_{timestamp}.json"

    process = subprocess.Popen(
        [
            sys.executable,
            str(PROJECT_ROOT / "enrich_investor_backlog.py"),
            str(backlog_path),
            str(output_path),
            str(limit),
        ],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    return {
        "exists": False,
        "last_modified": None,
        "summary": {
            "started": True,
            "pid": process.pid,
            "limit": limit,
            "output_file": output_path.name,
            "message": "Enrichment batch started in the background. Refresh history or Review Queue after it finishes.",
        },
        "items": [],
        "total_items": 0,
        "path": str(output_path),
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
    investor: str | None = None,
    sector: str | None = None,
    missing_sector: bool = False,
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

    if investor:
        query = query.filter(Investor.firm.ilike(f"%{investor}%"))

    if sector:
        query = query.filter(PortfolioCompany.sector.ilike(f"%{sector}%"))

    if missing_sector:
        query = query.filter(
            or_(
                PortfolioCompany.sector.is_(None),
                PortfolioCompany.sector == "",
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


@router.get("/blocklist")
def list_blocklist(
    q: str | None = None,
    db: Session = Depends(get_db),
):
    rows = (
        db.query(FailedUrl)
        .filter(FailedUrl.status == "blocked")
        .order_by(FailedUrl.last_attempt.desc().nullslast(), FailedUrl.id.desc())
        .all()
    )
    hosts = {}

    for row in rows:
        host = _hostname(row.url)

        if not host:
            continue

        if q and q.lower() not in host and q.lower() not in (row.url or "").lower():
            continue

        item = hosts.setdefault(
            host,
            {
                "host": host,
                "count": 0,
                "latest_reason": row.error_message,
                "latest_attempt": row.last_attempt,
                "sample_urls": [],
            },
        )
        item["count"] += 1

        if len(item["sample_urls"]) < 5:
            item["sample_urls"].append(row.url)

    return {
        "items": sorted(hosts.values(), key=lambda item: item["host"]),
        "total": len(hosts),
    }


@router.post("/blocklist/unblock")
def unblock_blocked_host(
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
):
    host = str(payload.get("host") or "").strip().lower().replace("www.", "")

    if not host:
        raise HTTPException(status_code=422, detail="Host is required")

    rows = db.query(FailedUrl).filter(FailedUrl.status == "blocked").all()
    updated = 0

    for row in rows:
        if _host_matches_url(host, row.url):
            row.status = "unblocked"
            updated += 1

    db.query(CrawlQueue).filter(CrawlQueue.status == "blocked").filter(
        or_(
            CrawlQueue.url.ilike(f"%://{host}%"),
            CrawlQueue.url.ilike(f"%://www.{host}%"),
        )
    ).update({"status": "pending"}, synchronize_session=False)

    db.commit()
    return {"host": host, "updated": updated}


@router.get("/enrichment/history")
def enrichment_history():
    exports_dir = PROJECT_ROOT / "exports"
    files = sorted(
        exports_dir.glob("investor_enrichment_results*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    items = []

    for path in files[:20]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        items.append(
            {
                "file": path.name,
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                "summary": payload.get("summary", {}),
            }
        )

    return {"items": items, "total": len(items)}


@router.post("/partners/repair-links")
def repair_partner_profile_links(db: Session = Depends(get_db)):
    updated = 0

    for partner in db.query(Partner).all():
        for field in ["linkedin_url", "twitter_url"]:
            value = getattr(partner, field)

            if not value:
                continue

            if field == "linkedin_url" and not _url_contains(value, ["linkedin.com"]):
                partner.source_url = partner.source_url or value
                setattr(partner, field, None)
                updated += 1

            if field == "twitter_url" and not _url_contains(value, ["twitter.com", "x.com"]):
                partner.source_url = partner.source_url or value
                setattr(partner, field, None)
                updated += 1

    db.commit()
    return {"updated": updated}


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


def _payload_is_blocked_or_failed(payload):
    if not isinstance(payload, dict):
        return False

    return bool(
        payload.get("blocked")
        or payload.get("extraction_failed")
        or payload.get("extraction_error")
    )


def _is_firecrawl_service_unavailable(reason):
    reason_text = str(reason or "").lower()
    unavailable_signals = [
        "localhost:3002",
        "127.0.0.1:3002",
        "connection refused",
        "actively refused",
        "failed to establish a new connection",
        "max retries exceeded with url: /v1/scrape",
        "winerror 10061",
    ]
    return any(signal in reason_text for signal in unavailable_signals)


def _firecrawl_unavailable_error(reason):
    return HTTPException(
        status_code=503,
        detail=(
            "Firecrawl is not running at localhost:3002. Start Docker/Firecrawl, "
            "wait until the API is healthy, then try Extract again."
        ),
    )


def _payload_has_insertable_investor_evidence(payload):
    if not isinstance(payload, dict):
        return False

    if _payload_is_blocked_or_failed(payload):
        return False

    firm = str(payload.get("firm", "") or "").strip()
    website = str(payload.get("website", "") or "").strip()
    source_url = str(payload.get("source_url", "") or "").strip()
    word_count = len(re.findall(r"[A-Za-z0-9]+", firm))
    punctuation_count = len(re.findall(r"[^A-Za-z0-9\s&.-]", firm))

    if word_count > 10 or punctuation_count > 2:
        return False

    return bool(firm and (website or source_url))


def _queue_manual_ingestion_parse_issue(
    db,
    url,
    markdown,
    parse_error,
    target_investor_id=None,
):
    return _create_manual_review_item(
        db=db,
        url=url,
        firm_name=_hostname(url),
        source_text=(markdown or "")[:4000],
        extracted_payload={
            "firm": _hostname(url),
            "website": url,
            "source_url": url,
            "focus_sectors": [],
            "investment_stage": [],
            "geography": [],
            "partners": [],
            "portfolio_companies": [],
            "contact_links": [],
            "parse_error": str(parse_error),
            "_target_investor_id": target_investor_id,
            "_target_source": "data_quality" if target_investor_id else "manual_url",
        },
        ai_decision="manual_url_parse_failed",
        ai_confidence=0.15,
        ai_reason=(
            "Extraction succeeded, but structured investor parsing failed. "
            "Edit the JSON before approving or reject this item."
        ),
    )


def _manual_failure_payload(
    url,
    reason,
    target_investor_id=None,
    target_source=None,
):
    return {
        "blocked": True,
        "extraction_failed": True,
        "source_url": url,
        "reason": reason,
        "extraction_error": reason,
        "_target_investor_id": target_investor_id,
        "_target_source": target_source or ("data_quality" if target_investor_id else "manual_url"),
    }


def _target_investor_id(payload):
    if not isinstance(payload, dict):
        return None

    target_id = payload.get("_target_investor_id")

    try:
        return int(target_id) if target_id else None
    except (TypeError, ValueError):
        return None


def _delete_target_investor_if_requested(db, review_item):
    payload = review_item.extracted_payload or {}
    target_id = _target_investor_id(payload)

    if not target_id:
        return None

    investor = db.query(Investor).filter(Investor.id == target_id).first()

    if not investor:
        return None

    db.query(Partner).filter(Partner.investor_id == investor.id).delete()
    db.query(PortfolioCompany).filter(PortfolioCompany.investor_id == investor.id).delete()
    db.delete(investor)
    return target_id


def _review_item_urls(review_item):
    payload = review_item.extracted_payload or {}
    urls = [
        review_item.url,
        payload.get("source_url") if isinstance(payload, dict) else "",
        payload.get("website") if isinstance(payload, dict) else "",
    ]

    return [
        url
        for url in dict.fromkeys(str(url or "").strip() for url in urls)
        if url.startswith(("http://", "https://"))
    ]


def _block_rejected_review_site(db, review_item, reason="Rejected by human review."):
    blocked_hosts = set()

    for url in _review_item_urls(review_item):
        host = _hostname(url)

        if not host:
            continue

        blocked_hosts.add(host)
        mark_url_blocked(
            url,
            f"Human rejected review item #{review_item.id}: {reason}",
        )

    for host in blocked_hosts:
        db.execute(
            text(
                """
                UPDATE crawl_queue
                SET status = 'blocked'
                WHERE status = 'pending'
                  AND (
                    lower(url) LIKE :host_with_scheme
                    OR lower(url) LIKE :host_without_www
                  )
                """
            ),
            {
                "host_with_scheme": f"%://{host}%",
                "host_without_www": f"%://www.{host}%",
            },
        )

    return sorted(blocked_hosts)


def _create_manual_review_item(
    db,
    url,
    firm_name,
    source_text,
    extracted_payload,
    ai_decision,
    ai_confidence,
    ai_reason,
):
    existing = (
        db.query(ReviewQueue)
        .filter(ReviewQueue.url == url)
        .filter(ReviewQueue.status == "pending")
        .order_by(ReviewQueue.created_at.desc().nullslast(), ReviewQueue.id.desc())
        .first()
    )

    if existing:
        existing.firm_name = existing.firm_name or firm_name
        existing.source_text = source_text or existing.source_text
        existing.extracted_payload = extracted_payload or existing.extracted_payload
        existing.ai_decision = ai_decision
        existing.ai_confidence = ai_confidence
        existing.ai_reason = ai_reason
        db.commit()
        db.refresh(existing)
        return existing

    item = ReviewQueue(
        url=url,
        firm_name=firm_name,
        source_text=source_text,
        extracted_payload=extracted_payload,
        ai_decision=ai_decision,
        ai_confidence=ai_confidence,
        ai_reason=ai_reason,
        status="pending",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/review-queue")
def list_review_queue(
    status: str | None = Query(default="pending"),
    q: str | None = None,
    domain: str | None = None,
    source: str | None = None,
    issue: str | None = None,
    min_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    max_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(ReviewQueue)

    if status and status != "all":
        query = query.filter(ReviewQueue.status == status)

    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                ReviewQueue.firm_name.ilike(pattern),
                ReviewQueue.url.ilike(pattern),
                ReviewQueue.ai_reason.ilike(pattern),
                ReviewQueue.human_reason.ilike(pattern),
            )
        )

    if domain:
        query = query.filter(ReviewQueue.url.ilike(f"%{domain}%"))

    if source:
        query = query.filter(ReviewQueue.ai_decision.ilike(f"%{source}%"))

    if issue == "blocked":
        query = query.filter(
            or_(
                ReviewQueue.ai_decision.ilike("%blocked%"),
                ReviewQueue.ai_decision.ilike("%failed%"),
            )
        )
    elif issue == "enrichment":
        query = query.filter(ReviewQueue.ai_decision.ilike("%enrichment%"))
    elif issue == "manual":
        query = query.filter(ReviewQueue.ai_decision.ilike("%manual%"))
    elif issue == "non_investor":
        query = query.filter(ReviewQueue.ai_decision.ilike("%not_investor%"))

    if min_confidence is not None:
        query = query.filter(ReviewQueue.ai_confidence >= min_confidence)

    if max_confidence is not None:
        query = query.filter(ReviewQueue.ai_confidence <= max_confidence)

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

    if _payload_is_blocked_or_failed(extracted_payload):
        raise HTTPException(
            status_code=422,
            detail=(
                "This item is blocked or extraction failed, so it cannot be approved. "
                "Reject it or extract a better alternate source URL."
            ),
        )

    if not _payload_has_insertable_investor_evidence(extracted_payload):
        raise HTTPException(
            status_code=422,
            detail=(
                "Approved item lacks enough investor evidence. "
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

    deleted_investor_id = _delete_target_investor_if_requested(db, item)
    human_reason = payload.get("human_reason", "") or "Rejected by human review."
    blocked_hosts = _block_rejected_review_site(db, item, human_reason)

    mark_reviewed(
        item,
        label="rejected",
        reason=human_reason,
        notes=(
            payload.get("reviewer_notes", "")
            or (
                f"Deleted source investor record #{deleted_investor_id} after rejection."
                if deleted_investor_id
                else (
                    f"Blocked site(s): {', '.join(blocked_hosts)}"
                    if blocked_hosts
                    else ""
                )
            )
        ),
    )
    db.commit()
    db.refresh(item)

    return _serialize_review_item(item)


@router.post("/review-queue/bulk-reject")
def bulk_reject_review_items(
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
):
    ids = payload.get("ids") or []
    reason = payload.get("human_reason", "Bulk rejected by human review.")

    if not ids:
        raise HTTPException(status_code=422, detail="No review item ids provided")

    items = (
        db.query(ReviewQueue)
        .filter(ReviewQueue.id.in_(ids))
        .filter(ReviewQueue.status == "pending")
        .all()
    )

    for item in items:
        _block_rejected_review_site(db, item, reason)
        mark_reviewed(
            item,
            label="rejected",
            reason=reason,
            notes=payload.get("reviewer_notes", ""),
        )

    db.commit()

    return {
        "updated": len(items),
    }


@router.post("/manual-ingestion/url")
def manual_url_ingestion(
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
):
    url = str(payload.get("url") or "").strip()
    target_investor_id = payload.get("investor_id")

    try:
        target_investor_id = int(target_investor_id) if target_investor_id else None
    except (TypeError, ValueError):
        target_investor_id = None

    if not url:
        raise HTTPException(status_code=422, detail="URL is required")

    try:
        markdown, extraction_reason = extract_manual_review_url_with_reason(url)
    except Exception as extraction_error:
        db.rollback()
        if _is_firecrawl_service_unavailable(extraction_error):
            raise _firecrawl_unavailable_error(extraction_error) from extraction_error

        try:
            item = _create_manual_review_item(
                db=db,
                url=url,
                firm_name=_hostname(url),
                source_text=str(extraction_error),
                extracted_payload=_manual_failure_payload(
                    url,
                    str(extraction_error),
                    target_investor_id=target_investor_id,
                ),
                ai_decision="blocked_extraction",
                ai_confidence=0.0,
                ai_reason=(
                    f"Blocked/extraction failed: {extraction_error}. "
                    "Reject this item or try a better alternate source URL."
                ),
            )
            return _serialize_review_item(item)
        except Exception as queue_error:
            db.rollback()
            raise HTTPException(
                status_code=503,
                detail=(
                    "Extraction failed and the review queue could not be updated. "
                    f"{queue_error}"
                ),
            ) from queue_error

    if not markdown:
        extraction_reason = extraction_reason or "No markdown extracted from URL."

        if _is_firecrawl_service_unavailable(extraction_reason):
            raise _firecrawl_unavailable_error(extraction_reason)

        item = _create_manual_review_item(
            db=db,
            url=url,
            firm_name=_hostname(url),
            source_text=extraction_reason,
            extracted_payload={
                **_manual_failure_payload(
                    url,
                    extraction_reason,
                    target_investor_id=target_investor_id,
                )
            },
            ai_decision="blocked_extraction",
            ai_confidence=0.0,
            ai_reason=(
                f"Blocked/extraction failed: {extraction_reason}. "
                "Reject this item or try a better alternate source URL."
            ),
        )
        return _serialize_review_item(item)

    try:
        parsed = parse_investor(markdown)
    except Exception as parse_error:
        return _serialize_review_item(
            _queue_manual_ingestion_parse_issue(
                db,
                url,
                markdown,
                parse_error,
                target_investor_id=target_investor_id,
            )
        )

    if not isinstance(parsed, dict):
        return _serialize_review_item(
            _queue_manual_ingestion_parse_issue(
                db,
                url,
                markdown,
                f"Parser returned {type(parsed).__name__}, expected object",
                target_investor_id=target_investor_id,
            )
        )

    parsed["source_url"] = parsed.get("source_url") or url
    parsed["website"] = parsed.get("website") or url
    parsed["_target_investor_id"] = target_investor_id
    parsed["_target_source"] = "data_quality" if target_investor_id else "manual_url"

    item = _create_manual_review_item(
        db=db,
        url=url,
        firm_name=parsed.get("firm", "") or _hostname(url),
        source_text=markdown[:4000],
        extracted_payload=parsed,
        ai_decision="manual_url_ingestion",
        ai_confidence=0.70 if _payload_has_insertable_investor_evidence(parsed) else 0.35,
        ai_reason="Manual URL ingestion result. Review before inserting.",
    )
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
        "blocked_urls": (
            db.query(FailedUrl)
            .filter(FailedUrl.status == "blocked")
            .count()
        ),
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
