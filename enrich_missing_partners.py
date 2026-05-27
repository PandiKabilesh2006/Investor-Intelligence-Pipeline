import argparse
import time
from datetime import datetime, timezone

from sqlalchemy import func

from app.database.db import SessionLocal
from app.database.models import Investor, Partner
from app.extraction.firecrawl_extract import extract_website
from app.extraction.html_extract import extract_website_with_requests
from app.parsing.gpt_parser import parse_investor


AGGREGATOR_OR_MEDIA_DOMAINS = [
    "cnbc.com",
    "globalventuring.com",
    "openvc.app",
    "saasvclist.com",
    "shizune.co",
    "signal.nfx.com",
    "vcsheet.com",
    "venturecapitaljournal.com",
]


def get_investors_without_partners(
    limit,
    firm=None,
    include_aggregators=False,
):
    session = SessionLocal()

    try:
        query = (
            session.query(Investor)
            .outerjoin(Partner)
            .group_by(Investor.id)
            .having(func.count(Partner.id) == 0)
            .filter(Investor.website.isnot(None))
            .filter(Investor.website != "")
            .order_by(Investor.updated_at.desc().nullslast(), Investor.id.asc())
        )

        if firm:
            query = query.filter(Investor.firm.ilike(f"%{firm}%"))

        if not include_aggregators:
            for domain in AGGREGATOR_OR_MEDIA_DOMAINS:
                query = query.filter(~Investor.website.ilike(f"%{domain}%"))

        if limit:
            query = query.limit(limit)

        return [
            {
                "id": investor.id,
                "firm": investor.firm,
                "website": investor.website,
                "source_url": investor.source_url,
                "focus_sectors": investor.focus_sectors or [],
                "investment_stage": investor.investment_stage or [],
                "geography": investor.geography or [],
                "contact_links": investor.contact_links or [],
            }
            for investor in query.all()
        ]

    finally:
        session.close()


def clean_partners(partners):
    cleaned = []
    seen = set()
    scraped_at = datetime.now(timezone.utc)
    blocked_names = {
        "john doe",
        "jane doe",
        "jane smith",
        "john smith",
        "sample name",
        "first last",
    }

    for partner in partners:
        if isinstance(partner, dict):
            name = str(partner.get("name") or "").strip()
            role = str(partner.get("role") or "").strip() or None
            title = str(
                partner.get("title") or partner.get("role") or ""
            ).strip() or None
            linkedin_url = str(partner.get("linkedin_url") or "").strip() or None
            twitter_url = str(partner.get("twitter_url") or "").strip() or None
            source_url = str(
                partner.get("source_url") or partner.get("linkedin_url") or ""
            ).strip() or None
            try:
                extraction_confidence = float(
                    partner.get("extraction_confidence") or 0.0
                )
            except (TypeError, ValueError):
                extraction_confidence = 0.0
        else:
            name = str(partner or "").strip()
            role = None
            title = None
            linkedin_url = None
            twitter_url = None
            source_url = None
            extraction_confidence = 0.0

        key = name.lower()

        if not key or key in blocked_names or key in seen:
            continue

        seen.add(key)

        if not extraction_confidence:
            if source_url and (role or title):
                extraction_confidence = 0.95
            elif role or title:
                extraction_confidence = 0.80
            else:
                extraction_confidence = 0.65

        cleaned.append(
            {
                "name": name,
                "role": role,
                "title": title or role,
                "linkedin_url": linkedin_url,
                "twitter_url": twitter_url,
                "source_url": source_url,
                "extraction_confidence": extraction_confidence,
                "scraped_at": scraped_at,
            }
        )

    return cleaned


def replace_partners(investor_id, partners):
    session = SessionLocal()

    try:
        investor = session.query(Investor).filter(Investor.id == investor_id).first()

        if not investor:
            raise ValueError(f"Investor not found: {investor_id}")

        session.query(Partner).filter(Partner.investor_id == investor_id).delete()

        for partner in partners:
            session.add(
                Partner(
                    investor_id=investor_id,
                    name=partner["name"],
                    role=partner.get("role"),
                    title=partner.get("title"),
                    linkedin_url=partner.get("linkedin_url"),
                    twitter_url=partner.get("twitter_url"),
                    source_url=partner.get("source_url"),
                    extraction_confidence=partner.get("extraction_confidence"),
                    scraped_at=partner.get("scraped_at"),
                    updated_at=datetime.now(timezone.utc),
                )
            )

        investor.updated_at = datetime.now(timezone.utc)
        session.commit()

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


def enrich_investor_partners(investor, dry_run=False):
    print(
        f"\nEnriching partners for {investor['firm']} | {investor['website']}"
    )

    markdown = extract_website(investor["website"])

    if not markdown:
        print("Firecrawl extraction empty; trying direct HTML fallback")
        markdown = extract_website_with_requests(investor["website"])

    if not markdown:
        print("No extractable content found")
        return False

    parsed = parse_investor(markdown)
    partners = clean_partners(parsed.get("partners") or [])

    if not partners:
        print("No partners found")
        return False

    print(
        f"Found {len(partners)} partners: "
        + ", ".join(
            partner.get("name", "")
            for partner in partners[:10]
        )
    )

    if dry_run:
        print("Dry run enabled; not writing to database")
        return True

    replace_partners(investor["id"], partners)
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Enrich investors that currently have no partner records."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum number of investors to process in this run.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Seconds to wait between investors.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and print results without writing to the database.",
    )
    parser.add_argument(
        "--firm",
        default=None,
        help="Only process investors whose firm name contains this text.",
    )
    parser.add_argument(
        "--include-aggregators",
        action="store_true",
        help=(
            "Also process media/listing URLs. Disabled by default because "
            "they often create low-confidence partner rows."
        ),
    )

    args = parser.parse_args()

    investors = get_investors_without_partners(
        args.limit,
        firm=args.firm,
        include_aggregators=args.include_aggregators,
    )

    print(
        f"Found {len(investors)} investors without partners to process."
    )

    updated = 0

    for investor in investors:
        try:
            if enrich_investor_partners(
                investor,
                dry_run=args.dry_run,
            ):
                updated += 1
        except Exception as error:
            print(
                f"Failed enriching {investor['firm']}: {error}"
            )

        time.sleep(args.delay)

    print(
        f"\nPartner enrichment complete. Investors with partners found: {updated}"
    )


if __name__ == "__main__":
    main()
