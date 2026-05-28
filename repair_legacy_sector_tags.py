import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import or_

from app.database.db import SessionLocal
from app.database.models import Investor
from app.extraction.firecrawl_extract import extract_website
from app.utils.normalization import clean_list_values, normalize_sector


EXPORT_DIR = Path("exports")
RAW_DIR = Path("raw_markdown")


B2B_HINTS = [
    "b2b",
    "business-to-business",
    "business to business",
    "enterprise software",
    "enterprise",
    "workflow",
    "productivity",
    "developer tools",
    "infrastructure software",
    "sales software",
    "marketing software",
    "hr software",
    "finance software",
    "vertical software",
]

SAAS_HINTS = [
    "saas",
    "software as a service",
    "subscription software",
    "cloud software",
    "cloud-based software",
    "vertical saas",
]


def _slug_url(url):
    if not url:
        return ""
    parsed = urlparse(url)
    raw = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".strip("/")
    return re.sub(r"[^a-zA-Z0-9]+", "_", raw).strip("_")


def _candidate_markdown_files(investor):
    candidates = []

    for url in [investor.source_url, investor.website]:
        slug = _slug_url(url)
        if slug:
            candidates.extend(RAW_DIR.glob(f"{slug}*.md"))

    if investor.website:
        hostname = urlparse(investor.website).hostname or ""
        hostname = hostname.lower().replace("www.", "")
        if hostname:
            host_slug = re.sub(r"[^a-zA-Z0-9]+", "_", hostname).strip("_")
            candidates.extend(RAW_DIR.glob(f"*{host_slug}*.md"))

    seen = set()
    unique = []
    for path in candidates:
        if path not in seen and path.exists():
            seen.add(path)
            unique.append(path)

    return unique


def _read_local_markdown(investor):
    chunks = []
    for path in _candidate_markdown_files(investor)[:5]:
        chunks.append(
            f"\n\n====================\nLOCAL FILE: {path.name}\n====================\n\n"
            f"{path.read_text(encoding='utf-8', errors='replace')}"
        )
    return "\n".join(chunks)


def _classify_b2b_saas(markdown):
    content = markdown.lower()
    b2b_hits = sorted({hint for hint in B2B_HINTS if hint in content})
    saas_hits = sorted({hint for hint in SAAS_HINTS if hint in content})

    sectors = []
    if b2b_hits:
        sectors.append("B2B")
    if saas_hits:
        sectors.append("SaaS")

    return sectors, {
        "b2b_hits": b2b_hits,
        "saas_hits": saas_hits,
    }


def _repair_sectors(current_sectors, inferred_sectors):
    repaired = []

    for sector in current_sectors or []:
        if str(sector).strip().lower() == "b2b saas":
            repaired.extend(inferred_sectors)
        else:
            repaired.extend(normalize_sector([sector]))

    return clean_list_values(repaired)


def repair_legacy_sector_tags(limit=25, apply=False, scrape_missing=False):
    EXPORT_DIR.mkdir(exist_ok=True)

    db = SessionLocal()
    results = []

    try:
        query = (
            db.query(Investor)
            .filter(
                or_(
                    Investor.focus_sectors.any("B2B SaaS"),
                    Investor.focus_sectors.any("Enterprise AI"),
                )
            )
            .order_by(Investor.updated_at.desc().nullslast(), Investor.id.asc())
        )

        investors = query.limit(limit).all() if limit else query.all()

        for investor in investors:
            local_markdown = _read_local_markdown(investor)
            markdown_source = "local"
            markdown = local_markdown

            if not markdown and scrape_missing:
                scrape_url = investor.website or investor.source_url
                if scrape_url:
                    markdown = extract_website(scrape_url) or ""
                    markdown_source = "scraped"

            inferred, evidence = _classify_b2b_saas(markdown)
            current = investor.focus_sectors or []
            repaired = _repair_sectors(current, inferred)

            changed = repaired != current

            if apply and changed:
                investor.focus_sectors = repaired
                investor.updated_at = datetime.now(timezone.utc)

            results.append(
                {
                    "investor_id": investor.id,
                    "firm": investor.firm,
                    "current_focus_sectors": current,
                    "repaired_focus_sectors": repaired,
                    "changed": changed,
                    "markdown_source": markdown_source if markdown else "none",
                    "evidence": evidence,
                }
            )

        if apply:
            db.commit()
        else:
            db.rollback()

    finally:
        db.close()

    output_path = EXPORT_DIR / "legacy_sector_tag_repair_report.json"
    output_path.write_text(
        json.dumps(
            {
                "apply": apply,
                "scrape_missing": scrape_missing,
                "selected_records": len(results),
                "changed_records": sum(1 for result in results if result["changed"]),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "results": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Report exported to {output_path}")
    print(f"Selected records: {len(results)}")
    print(f"Changed records: {sum(1 for result in results if result['changed'])}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Repair legacy B2B SaaS/Enterprise AI sector tags."
    )
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--scrape-missing", action="store_true")
    args = parser.parse_args()

    repair_legacy_sector_tags(
        limit=args.limit,
        apply=args.apply,
        scrape_missing=args.scrape_missing,
    )
