import json
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse


PARTNER_PATHS = [
    "/team",
    "/people",
    "/partners",
    "/leadership",
    "/investment-team",
    "/our-team",
]

PORTFOLIO_PATHS = [
    "/portfolio",
    "/companies",
    "/investments",
    "/portfolio-companies",
]

METADATA_PATHS = [
    "/about",
    "/thesis",
    "/focus",
    "/investment-strategy",
    "/investment-thesis",
]

CONTACT_PATHS = [
    "/contact",
    "/get-in-touch",
]

MEDIA_DOMAIN_KEYWORDS = (
    "cnbc",
    "forbes",
    "reuters",
    "bloomberg",
    "businessinsider",
    "techcrunch",
    "fortune",
    "wsj",
    "nytimes",
    "economictimes",
    "moneycontrol",
    "medium.com",
    "substack.com",
)

PUBLIC_SECTOR_KEYWORDS = (
    ".gov",
    "gov.in",
    "ministry",
    "government",
    "aayog",
    "investment grid",
    "invest india",
    "indiaai",
    "public policy",
    "economic development",
    "investment opportunities",
)


def _hostname(url):
    if not url:
        return ""

    try:
        return urlparse(url).hostname or ""
    except ValueError:
        return ""


def _website_base(url):
    if not url:
        return ""

    try:
        parsed = urlparse(url)
    except ValueError:
        return ""

    if not parsed.scheme or not parsed.netloc:
        return ""

    return f"{parsed.scheme}://{parsed.netloc}"


def _build_candidate_urls(base_url, paths):
    if not base_url:
        return []

    return [f"{base_url}{path}" for path in paths]


def _build_queries(record):
    firm = record["firm"]
    geography = record["geography"][0] if record["geography"] else ""
    geography_suffix = f" in {geography}" if geography else ""
    queries = []

    missing = set(record["missing_fields"])

    if "partners" in missing:
        queries.extend(
            [
                f"{firm} team{geography_suffix}",
                f"{firm} partners{geography_suffix}",
                f"{firm} leadership{geography_suffix}",
            ]
        )

    if "portfolio_companies" in missing:
        queries.extend(
            [
                f"{firm} portfolio{geography_suffix}",
                f"{firm} portfolio companies{geography_suffix}",
                f"{firm} investments{geography_suffix}",
            ]
        )

    if {"focus_sectors", "investment_stage", "geography"} & missing:
        queries.extend(
            [
                f"{firm} investment thesis",
                f"{firm} focus sectors",
                f"{firm} investment stage",
                f"{firm} about",
            ]
        )

    if "contact_links" in missing:
        queries.append(f"{firm} contact")

    return list(dict.fromkeys(query.strip() for query in queries if query.strip()))


def _build_page_targets(record):
    base_url = _website_base(record["website"] or record["source_url"])
    missing = set(record["missing_fields"])
    targets = []

    if "partners" in missing:
        targets.extend(
            {
                "type": "partners",
                "url": url,
            }
            for url in _build_candidate_urls(base_url, PARTNER_PATHS)
        )

    if "portfolio_companies" in missing:
        targets.extend(
            {
                "type": "portfolio",
                "url": url,
            }
            for url in _build_candidate_urls(base_url, PORTFOLIO_PATHS)
        )

    if {"focus_sectors", "investment_stage", "geography"} & missing:
        targets.extend(
            {
                "type": "metadata",
                "url": url,
            }
            for url in _build_candidate_urls(base_url, METADATA_PATHS)
        )

    if "contact_links" in missing:
        targets.extend(
            {
                "type": "contact",
                "url": url,
            }
            for url in _build_candidate_urls(base_url, CONTACT_PATHS)
        )

    return targets


def _is_suspicious_record(record):
    haystack = " ".join(
        [
            record.get("firm", ""),
            record.get("website", ""),
            record.get("source_url", ""),
        ]
    ).lower()

    if any(keyword in haystack for keyword in MEDIA_DOMAIN_KEYWORDS):
        return True

    if any(keyword in haystack for keyword in PUBLIC_SECTOR_KEYWORDS):
        return True

    return False


STATUS_PRIORITY = {
    "critical": 0,
    "thin": 1,
    "usable": 2,
    "strong": 3,
}


def build_backlog(audit_path, output_path, min_score=6, limit=None):
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    records = audit.get("records", [])

    all_candidates = [
        record
        for record in records
        if (
            record["score"] < min_score
            and record["status"] != "strong"
            and record["missing_fields"]
        )
    ]

    skipped_suspicious = [
        record
        for record in all_candidates
        if _is_suspicious_record(record)
    ]

    candidates = [
        record
        for record in all_candidates
        if not _is_suspicious_record(record)
    ]

    candidates.sort(
        key=lambda record: (
            STATUS_PRIORITY.get(record["status"], 9),
            record["score"],
            -record["partner_count"],
            -record["portfolio_company_count"],
            record["firm"].lower(),
        )
    )

    if limit is not None:
        candidates = candidates[:limit]

    backlog = []

    for record in candidates:
        backlog.append(
            {
                "investor_id": record["investor_id"],
                "firm": record["firm"],
                "score": record["score"],
                "status": record["status"],
                "website": record["website"],
                "source_url": record["source_url"],
                "domain": _hostname(record["website"] or record["source_url"]),
                "missing_fields": record["missing_fields"],
                "partner_count": record["partner_count"],
                "portfolio_company_count": record["portfolio_company_count"],
                "queries": _build_queries(record),
                "page_targets": _build_page_targets(record),
            }
        )

    summary = {
        "audit_source": str(audit_path),
        "selected_records": len(backlog),
        "skipped_suspicious_records": len(skipped_suspicious),
        "min_score_threshold": min_score,
        "status_order": ["critical", "thin", "usable"],
        "status_breakdown": dict(
            Counter(item["status"] for item in backlog)
        ),
        "missing_field_breakdown": dict(
            Counter(
                field
                for item in backlog
                for field in item["missing_fields"]
            )
        ),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "summary": summary,
                "backlog": backlog,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"Enrichment backlog exported to {output_path}")
    print(f"Selected records: {summary['selected_records']}")
    print(f"Status breakdown: {summary['status_breakdown']}")
    print(f"Missing field breakdown: {summary['missing_field_breakdown']}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        audit_path = Path(sys.argv[1])
    else:
        audit_path = Path("exports/investor_coverage_audit.json")

    if len(sys.argv) > 2:
        output_path = Path(sys.argv[2])
    else:
        output_path = Path("exports/investor_enrichment_backlog.json")

    limit = int(sys.argv[3]) if len(sys.argv) > 3 else None

    build_backlog(
        audit_path=audit_path,
        output_path=output_path,
        limit=limit,
    )
