import argparse
import time
from datetime import datetime, timezone

from sqlalchemy import or_

from app.database.db import SessionLocal
from app.database.models import Investor, Partner
from app.extraction.firecrawl_extract import extract_website
from app.extraction.html_extract import extract_website_with_requests
from app.parsing.gpt_parser import parse_investor
from enrich_missing_partners import (
    AGGREGATOR_OR_MEDIA_DOMAINS,
    clean_partners,
)


def get_investors_with_incomplete_partners(
    limit,
    firm=None,
    include_aggregators=False,
):
    session = SessionLocal()

    try:
        query = (
            session.query(Investor)
            .join(Partner)
            .filter(Investor.website.isnot(None))
            .filter(Investor.website != "")
            .filter(
                or_(
                    Partner.role.is_(None),
                    Partner.role == "",
                    Partner.title.is_(None),
                    Partner.title == "",
                    Partner.source_url.is_(None),
                    Partner.source_url == "",
                )
            )
            .group_by(Investor.id)
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
            }
            for investor in query.all()
        ]

    finally:
        session.close()


def merge_partner_metadata(investor_id, parsed_partners):
    session = SessionLocal()
    now = datetime.now(timezone.utc)

    try:
        existing = {
            (partner.name or "").strip().lower(): partner
            for partner in (
                session.query(Partner)
                .filter(Partner.investor_id == investor_id)
                .all()
            )
        }

        updated = 0

        for parsed_partner in parsed_partners:
            key = (parsed_partner.get("name") or "").strip().lower()
            partner = existing.get(key)

            if not partner:
                continue

            partner.role = partner.role or parsed_partner.get("role")
            partner.title = partner.title or parsed_partner.get("title")
            partner.linkedin_url = (
                partner.linkedin_url or parsed_partner.get("linkedin_url")
            )
            partner.twitter_url = (
                partner.twitter_url or parsed_partner.get("twitter_url")
            )
            partner.source_url = partner.source_url or parsed_partner.get("source_url")
            partner.extraction_confidence = (
                parsed_partner.get("extraction_confidence")
                or partner.extraction_confidence
                or 0.80
            )
            partner.scraped_at = parsed_partner.get("scraped_at") or now
            partner.updated_at = now
            updated += 1

        session.commit()
        return updated

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


def count_matching_existing_partners(investor_id, parsed_partners):
    session = SessionLocal()

    try:
        existing = {
            (partner.name or "").strip().lower()
            for partner in (
                session.query(Partner.name)
                .filter(Partner.investor_id == investor_id)
                .all()
            )
        }

        return sum(
            1
            for partner in parsed_partners
            if (partner.get("name") or "").strip().lower() in existing
        )

    finally:
        session.close()


def enrich_existing_partner_metadata(investor, dry_run=False):
    print(
        f"\nEnriching existing partner metadata for "
        f"{investor['firm']} | {investor['website']}"
    )

    markdown = extract_website(investor["website"])

    if not markdown:
        print("Firecrawl extraction empty; trying direct HTML fallback")
        markdown = extract_website_with_requests(investor["website"])

    if not markdown:
        print("No extractable content found")
        return 0

    parsed = parse_investor(markdown)
    parsed_partners = clean_partners(parsed.get("partners") or [])

    if not parsed_partners:
        print("No partner metadata found")
        return 0

    print(
        f"Parsed {len(parsed_partners)} partners: "
        + ", ".join(
            partner.get("name", "")
            for partner in parsed_partners[:10]
        )
    )

    if dry_run:
        matched = count_matching_existing_partners(
            investor["id"],
            parsed_partners,
        )
        print(
            f"Dry run enabled; {matched} parsed partners match "
            "existing database rows"
        )
        return matched

    updated = merge_partner_metadata(investor["id"], parsed_partners)
    print(f"Updated {updated} existing partner rows")
    return updated


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Fill role/title/source/confidence metadata on existing partners."
        )
    )
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--firm", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--include-aggregators", action="store_true")

    args = parser.parse_args()

    investors = get_investors_with_incomplete_partners(
        args.limit,
        firm=args.firm,
        include_aggregators=args.include_aggregators,
    )

    print(f"Found {len(investors)} investors with incomplete partner metadata.")

    updated = 0

    for investor in investors:
        try:
            updated += enrich_existing_partner_metadata(
                investor,
                dry_run=args.dry_run,
            )
        except Exception as error:
            print(f"Failed enriching {investor['firm']}: {error}")

        time.sleep(args.delay)

    print(f"\nExisting partner metadata enrichment complete. Rows updated: {updated}")


if __name__ == "__main__":
    main()
