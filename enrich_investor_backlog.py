import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy.orm import selectinload

from app.database.db import SessionLocal
from app.database.models import Investor
from app.extraction.firecrawl_extract import scrape_single_page
from app.parsing.gpt_parser import parse_investor
from app.search.tavily_search import search_investors
from app.utils.normalization import normalize_firm_key
from insert_into_db import insert_investor_data


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
        markdown = scrape_single_page(url)

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

    payload = dict(parsed)
    payload["firm"] = investor.firm
    payload["website"] = payload.get("website") or investor.website or ""
    payload["source_url"] = payload.get("source_url") or investor.source_url or (source_urls[0] if source_urls else "")
    return payload


def enrich_from_backlog(backlog_path, output_path, limit=10):
    backlog_data = json.loads(backlog_path.read_text(encoding="utf-8"))
    backlog_items = backlog_data.get("backlog", [])[:limit]
    session = SessionLocal()
    results = []

    try:
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
                results.append(
                    {
                        "investor_id": investor.id,
                        "firm": investor.firm,
                        "status": "no_content",
                        "attempted_urls": candidate_urls[:8],
                        "search_urls": search_urls,
                    }
                )
                continue

            combined_markdown = _combine_markdown(snippets)
            parsed = parse_investor(combined_markdown)
            payload = _validated_payload(
                item=item,
                investor=investor,
                parsed=parsed,
                source_urls=[snippet["url"] for snippet in snippets],
            )

            if not payload:
                results.append(
                    {
                        "investor_id": investor.id,
                        "firm": investor.firm,
                        "status": "firm_validation_failed",
                        "parsed_firm": parsed.get("firm", ""),
                        "source_urls": [snippet["url"] for snippet in snippets],
                    }
                )
                continue

            insert_investor_data(payload)

            results.append(
                {
                    "investor_id": investor.id,
                    "firm": investor.firm,
                    "status": "updated",
                    "source_urls": [snippet["url"] for snippet in snippets],
                    "parsed_firm": parsed.get("firm", ""),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
    finally:
        session.close()

    summary = {
        "backlog_source": str(backlog_path),
        "processed": len(results),
        "updated": sum(1 for result in results if result["status"] == "updated"),
        "no_content": sum(1 for result in results if result["status"] == "no_content"),
        "firm_validation_failed": sum(1 for result in results if result["status"] == "firm_validation_failed"),
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
