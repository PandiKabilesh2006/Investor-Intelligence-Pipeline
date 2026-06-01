import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy.orm import selectinload

from app.database.db import SessionLocal
from app.database.models import Investor, ReviewQueue
from app.extraction.firecrawl_extract import scrape_single_page
from app.parsing.gpt_parser import parse_investor
from app.search.tavily_search import search_investors
from app.utils.normalization import normalize_firm_key


HIGH_SIGNAL_HINTS = (
    "team",
    "people",
    "partners",
    "leadership",
    "portfolio",
    "companies",
    "investments",
    "about",
    "thesis",
    "focus",
    "contact",
)

INVESTOR_EVIDENCE_TERMS = (
    "venture capital",
    "vc firm",
    "investment firm",
    "investment fund",
    "venture fund",
    "growth equity",
    "private equity",
    "seed investor",
    "series a investor",
    "startup investor",
    "invests in startups",
    "invest in startups",
    "backs founders",
    "back founders",
    "backed by",
    "portfolio companies",
    "our portfolio",
    "selected investments",
    "investment team",
    "managing partner",
    "general partner",
)

INVESTMENT_ROLE_TERMS = (
    "partner",
    "principal",
    "investment",
    "venture",
    "managing director",
    "general partner",
)


def _hostname(url):
    if not url:
        return ""

    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def _is_same_domain(url, domains):
    hostname = _hostname(url)

    if not hostname:
        return False

    return any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in domains
        if domain
    )


def _select_search_urls(item, domains, max_urls=4):
    selected = []
    seen = set()

    for query in item.get("queries", []):
        try:
            search_results = search_investors(query=query, max_pages=2)
        except Exception:
            continue

        for result in search_results.get("results", []):
            url = (result.get("url") or "").strip()

            if not url or url in seen:
                continue

            seen.add(url)
            same_domain = _is_same_domain(url, domains)
            signal = any(hint in url.lower() for hint in HIGH_SIGNAL_HINTS)

            if same_domain or signal:
                selected.append(url)

            if len(selected) >= max_urls:
                return selected

    return selected


def _extract_candidate_markdown(candidate_urls, max_successes=4):
    snippets = []

    for url in candidate_urls:
        try:
            markdown = scrape_single_page(url)
        except Exception:
            continue

        if not markdown or len(markdown.strip()) < 200:
            continue

        snippets.append(
            {
                "url": url,
                "markdown": markdown,
            }
        )

        if len(snippets) >= max_successes:
            break

    return snippets


def _combine_markdown(snippets):
    return "\n\n".join(
        [
            (
                "\n\n====================\n"
                f"URL: {snippet['url']}\n"
                "====================\n\n"
                f"{snippet['markdown']}"
            )
            for snippet in snippets
        ]
    )


def _load_investor(session, investor_id):
    return (
        session.query(Investor)
        .options(
            selectinload(Investor.partners),
            selectinload(Investor.portfolio_companies),
        )
        .filter(Investor.id == investor_id)
        .first()
    )


def _validated_payload(item, investor, parsed, source_urls):
    expected_key = normalize_firm_key(item["firm"])
    parsed_firm = str(parsed.get("firm", "")).strip()
    parsed_key = normalize_firm_key(parsed_firm)

    trusted_domains = {
        _hostname(investor.website),
        _hostname(investor.source_url),
        *[_hostname(url) for url in source_urls],
    }
    trusted_domains = {domain for domain in trusted_domains if domain}

    parsed_website = parsed.get("website", "") or investor.website or investor.source_url or ""
    parsed_website_domain = _hostname(parsed_website)

    same_firm = parsed_key and parsed_key == expected_key
    trusted_source = parsed_website_domain in trusted_domains or any(
        _hostname(url) in trusted_domains
        for url in source_urls
    )

    if not same_firm and not trusted_source:
        return None

    payload = _public_payload(parsed)
    payload["firm"] = investor.firm
    payload["website"] = payload.get("website") or investor.website or ""
    payload["source_url"] = payload.get("source_url") or investor.source_url or (source_urls[0] if source_urls else "")
    payload["_target_investor_id"] = investor.id
    payload["_target_source"] = "enrichment_backlog"
    return payload


def _public_payload(parsed):
    return {
        "firm": parsed.get("firm", ""),
        "website": parsed.get("website", ""),
        "partners": parsed.get("partners", []) or [],
        "geography": parsed.get("geography", []) or [],
        "source_url": parsed.get("source_url", ""),
        "contact_links": parsed.get("contact_links", []) or [],
        "focus_sectors": parsed.get("focus_sectors", []) or [],
        "investment_stage": parsed.get("investment_stage", []) or [],
        "portfolio_companies": parsed.get("portfolio_companies", []) or [],
    }


def _simple_failure_payload(investor, reason, parsed_firm=""):
    return {
        "firm": investor.firm,
        "website": investor.website or "",
        "partners": [],
        "geography": [],
        "source_url": investor.source_url or investor.website or "",
        "contact_links": [],
        "focus_sectors": [],
        "investment_stage": [],
        "portfolio_companies": [],
        "blocked": True,
        "extraction_failed": True,
        "reason": reason,
        "parsed_firm": parsed_firm,
        "_target_investor_id": investor.id,
        "_target_source": "enrichment_backlog",
    }


def _has_investor_evidence(parsed, combined_markdown):
    text = (combined_markdown or "").lower()

    if parsed.get("investment_stage") or parsed.get("portfolio_companies"):
        return True

    for partner in parsed.get("partners", []) or []:
        role_text = " ".join(
            [
                str(partner.get("role", "")),
                str(partner.get("title", "")),
            ]
        ).lower()

        if any(term in role_text for term in INVESTMENT_ROLE_TERMS):
            return True

    evidence_hits = sum(
        1
        for term in INVESTOR_EVIDENCE_TERMS
        if term in text
    )

    if evidence_hits >= 2:
        return True

    if "investor relations" in text and evidence_hits < 2:
        return False

    return False


def _queue_enrichment_review_item(
    session,
    investor,
    item,
    payload,
    source_urls,
    source_text,
    ai_decision="enrichment_needs_review",
    ai_confidence=0.65,
    ai_reason="Enrichment result requires human approval before updating the investor database.",
):
    review_url = (
        source_urls[0]
        if source_urls
        else investor.source_url
        or investor.website
        or ""
    )

    existing = (
        session.query(ReviewQueue)
        .filter(ReviewQueue.url == review_url)
        .filter(ReviewQueue.status == "pending")
        .order_by(ReviewQueue.created_at.desc().nullslast(), ReviewQueue.id.desc())
        .first()
    )

    if existing:
        existing.firm_name = investor.firm
        existing.source_text = source_text[:4000]
        existing.extracted_payload = payload
        existing.ai_decision = ai_decision
        existing.ai_confidence = ai_confidence
        existing.ai_reason = ai_reason
        return existing

    review_item = ReviewQueue(
        url=review_url,
        firm_name=investor.firm,
        source_text=source_text[:4000],
        extracted_payload=payload,
        ai_decision=ai_decision,
        ai_confidence=ai_confidence,
        ai_reason=ai_reason,
        status="pending",
    )
    session.add(review_item)
    return review_item


def _pending_enrichment_investor_ids(session):
    pending_ids = set()
    pending_items = (
        session.query(ReviewQueue.extracted_payload)
        .filter(ReviewQueue.status == "pending")
        .all()
    )

    for (payload,) in pending_items:
        if not isinstance(payload, dict):
            continue

        if payload.get("_target_source") != "enrichment_backlog":
            continue

        investor_id = payload.get("_target_investor_id")
        if investor_id is None:
            continue

        try:
            pending_ids.add(int(investor_id))
        except (TypeError, ValueError):
            continue

    return pending_ids


def enrich_from_backlog(backlog_path, output_path, limit=10):
    backlog_data = json.loads(backlog_path.read_text(encoding="utf-8"))
    all_backlog_items = backlog_data.get("backlog", [])
    session = SessionLocal()
    results = []
    skipped_pending_review = 0
    skipped_missing_investor = 0

    try:
        pending_review_ids = _pending_enrichment_investor_ids(session)
        existing_investor_ids = {
            investor_id
            for (investor_id,) in session.query(Investor.id).all()
        }
        backlog_items = []

        for item in all_backlog_items:
            investor_id = item.get("investor_id")

            if investor_id not in existing_investor_ids:
                skipped_missing_investor += 1
                continue

            if investor_id in pending_review_ids:
                skipped_pending_review += 1
                continue

            backlog_items.append(item)

            if len(backlog_items) >= limit:
                break

        for item in backlog_items:
            investor = _load_investor(session, item["investor_id"])

            if not investor:
                results.append(
                    {
                        "investor_id": item["investor_id"],
                        "firm": item["firm"],
                        "status": "skipped_missing_investor",
                    }
                )
                continue

            candidate_urls = [
                target["url"]
                for target in item.get("page_targets", [])
            ]

            domains = {
                _hostname(investor.website),
                _hostname(investor.source_url),
            }
            domains = {domain for domain in domains if domain}

            snippets = _extract_candidate_markdown(candidate_urls)

            search_urls = []
            if not snippets:
                search_urls = _select_search_urls(item, domains)
                snippets = _extract_candidate_markdown(search_urls)

            if not snippets:
                failure_payload = _simple_failure_payload(
                    investor,
                    "No usable content extracted during enrichment.",
                )
                _queue_enrichment_review_item(
                    session=session,
                    investor=investor,
                    item=item,
                    payload=failure_payload,
                    source_urls=candidate_urls[:1] or search_urls[:1],
                    source_text=json.dumps(failure_payload, indent=2),
                    ai_decision="enrichment_no_content",
                    ai_confidence=0.0,
                    ai_reason=(
                        "Enrichment touched this record but could not extract usable content. "
                        "Reject it or provide a better source URL."
                    ),
                )
                session.commit()
                results.append(
                    {
                        "investor_id": investor.id,
                        "firm": investor.firm,
                        "status": "queued_no_content_review",
                        "attempted_urls": candidate_urls[:8],
                        "search_urls": search_urls,
                    }
                )
                continue

            combined_markdown = _combine_markdown(snippets)
            try:
                parsed = parse_investor(combined_markdown)
            except Exception as exc:
                failure_payload = _simple_failure_payload(
                    investor,
                    f"LLM parsing failed during enrichment: {exc}",
                )
                _queue_enrichment_review_item(
                    session=session,
                    investor=investor,
                    item=item,
                    payload=failure_payload,
                    source_urls=[snippet["url"] for snippet in snippets],
                    source_text=combined_markdown,
                    ai_decision="enrichment_parse_failed",
                    ai_confidence=0.0,
                    ai_reason=(
                        "Enrichment extracted content, but parsing failed. "
                        "Reject it, retry later, or edit manually if the source is useful."
                    ),
                )
                session.commit()
                results.append(
                    {
                        "investor_id": investor.id,
                        "firm": investor.firm,
                        "status": "queued_parse_failed_review",
                        "error": str(exc),
                        "source_urls": [snippet["url"] for snippet in snippets],
                    }
                )
                continue

            if not _has_investor_evidence(parsed, combined_markdown):
                failure_payload = _simple_failure_payload(
                    investor,
                    (
                        "Enrichment content did not contain enough evidence that "
                        "this record is an investment firm or fund."
                    ),
                    parsed_firm=parsed.get("firm", ""),
                )
                _queue_enrichment_review_item(
                    session=session,
                    investor=investor,
                    item=item,
                    payload=failure_payload,
                    source_urls=[snippet["url"] for snippet in snippets],
                    source_text=combined_markdown,
                    ai_decision="enrichment_not_investor",
                    ai_confidence=0.0,
                    ai_reason=(
                        "Enrichment touched this record, but the extracted pages look "
                        "like a company/corporate website rather than an investor. "
                        "Reject it unless you have better evidence."
                    ),
                )
                session.commit()
                results.append(
                    {
                        "investor_id": investor.id,
                        "firm": investor.firm,
                        "status": "queued_not_investor_review",
                        "parsed_firm": parsed.get("firm", ""),
                        "source_urls": [snippet["url"] for snippet in snippets],
                    }
                )
                continue

            payload = _validated_payload(
                item=item,
                investor=investor,
                parsed=parsed,
                source_urls=[snippet["url"] for snippet in snippets],
            )

            if not payload:
                failure_payload = _simple_failure_payload(
                    investor,
                    "Parsed content did not validate as the expected investor firm.",
                    parsed_firm=parsed.get("firm", ""),
                )
                _queue_enrichment_review_item(
                    session=session,
                    investor=investor,
                    item=item,
                    payload=failure_payload,
                    source_urls=[snippet["url"] for snippet in snippets],
                    source_text=combined_markdown,
                    ai_decision="enrichment_validation_failed",
                    ai_confidence=0.0,
                    ai_reason=(
                        "Enrichment touched this record, but parsed content did not "
                        "validate as the expected investor firm. Reject it or edit manually."
                    ),
                )
                session.commit()
                results.append(
                    {
                        "investor_id": investor.id,
                        "firm": investor.firm,
                        "status": "queued_validation_failed_review",
                        "parsed_firm": parsed.get("firm", ""),
                        "source_urls": [snippet["url"] for snippet in snippets],
                    }
                )
                continue

            review_item = _queue_enrichment_review_item(
                session=session,
                investor=investor,
                item=item,
                payload=payload,
                source_urls=[snippet["url"] for snippet in snippets],
                source_text=combined_markdown,
            )
            session.commit()
            session.refresh(review_item)

            results.append(
                {
                    "investor_id": investor.id,
                    "firm": investor.firm,
                    "status": "queued_review",
                    "review_item_id": review_item.id,
                    "source_urls": [snippet["url"] for snippet in snippets],
                    "parsed_firm": parsed.get("firm", ""),
                    "queued_at": datetime.now(timezone.utc).isoformat(),
                }
            )
    finally:
        session.close()

    summary = {
        "backlog_source": str(backlog_path),
        "processed": len(results),
        "skipped_pending_review": skipped_pending_review,
        "skipped_missing_investor": skipped_missing_investor,
        "queued_review": sum(1 for result in results if result["status"] == "queued_review"),
        "queued_no_content_review": sum(1 for result in results if result["status"] == "queued_no_content_review"),
        "queued_validation_failed_review": sum(1 for result in results if result["status"] == "queued_validation_failed_review"),
        "queued_not_investor_review": sum(1 for result in results if result["status"] == "queued_not_investor_review"),
        "queued_parse_failed_review": sum(1 for result in results if result["status"] == "queued_parse_failed_review"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "summary": summary,
                "results": results,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"Enrichment results exported to {output_path}")
    print(summary)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        backlog = Path(sys.argv[1])
    else:
        backlog = Path("exports/investor_enrichment_backlog.json")

    if len(sys.argv) > 2:
        output = Path(sys.argv[2])
    else:
        output = Path("exports/investor_enrichment_results.json")

    batch_limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10

    enrich_from_backlog(backlog, output, batch_limit)
