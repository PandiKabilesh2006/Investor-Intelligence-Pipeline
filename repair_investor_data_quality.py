import argparse

from app.database.db import SessionLocal
from app.database.models import Investor, Partner, PortfolioCompany
from app.utils.normalization import (
    merge_clean_lists,
    normalize_firm_key,
    normalize_geography,
    normalize_sector,
    normalize_stage,
)


def record_score(investor):
    return sum(
        [
            bool(investor.website),
            bool(investor.source_url),
            len(investor.focus_sectors or []),
            len(investor.investment_stage or []),
            len(investor.geography or []),
            len(investor.contact_links or []),
        ]
    )


def normalize_existing_rows(session, apply_changes):
    investors = session.query(Investor).all()
    updated = 0

    for investor in investors:
        focus_sectors = normalize_sector(investor.focus_sectors)
        investment_stage = normalize_stage(investor.investment_stage)
        geography = normalize_geography(investor.geography)
        contact_links = merge_clean_lists(investor.contact_links)

        changed = (
            focus_sectors != (investor.focus_sectors or [])
            or investment_stage != (investor.investment_stage or [])
            or geography != (investor.geography or [])
            or contact_links != (investor.contact_links or [])
        )

        if changed:
            updated += 1

            if apply_changes:
                investor.focus_sectors = focus_sectors
                investor.investment_stage = investment_stage
                investor.geography = geography
                investor.contact_links = contact_links

    return updated


def merge_duplicate_investors(session, apply_changes):
    investors = session.query(Investor).all()
    groups = {}

    for investor in investors:
        key = normalize_firm_key(investor.firm)

        if key:
            groups.setdefault(key, []).append(investor)

    duplicate_groups = [
        group
        for group in groups.values()
        if len(group) > 1
    ]

    merge_count = 0

    for group in duplicate_groups:
        canonical = sorted(
            group,
            key=lambda investor: (-record_score(investor), investor.id),
        )[0]
        duplicates = [
            investor
            for investor in group
            if investor.id != canonical.id
        ]

        print(
            f"Duplicate group: {canonical.firm} <- "
            f"{', '.join(investor.firm for investor in duplicates)}"
        )

        merge_count += len(duplicates)

        if not apply_changes:
            continue

        for duplicate in duplicates:
            canonical.website = canonical.website or duplicate.website
            canonical.source_url = canonical.source_url or duplicate.source_url
            canonical.focus_sectors = normalize_sector(
                merge_clean_lists(canonical.focus_sectors, duplicate.focus_sectors)
            )
            canonical.investment_stage = normalize_stage(
                merge_clean_lists(canonical.investment_stage, duplicate.investment_stage)
            )
            canonical.geography = normalize_geography(
                merge_clean_lists(canonical.geography, duplicate.geography)
            )
            canonical.contact_links = merge_clean_lists(
                canonical.contact_links,
                duplicate.contact_links,
            )

            session.query(Partner).filter(
                Partner.investor_id == duplicate.id
            ).update(
                {"investor_id": canonical.id},
                synchronize_session=False,
            )
            session.query(PortfolioCompany).filter(
                PortfolioCompany.investor_id == duplicate.id
            ).update(
                {"investor_id": canonical.id},
                synchronize_session=False,
            )
            session.delete(duplicate)

    return merge_count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually update and merge records. Without this, only previews changes.",
    )
    args = parser.parse_args()

    session = SessionLocal()

    try:
        updated = normalize_existing_rows(session, args.apply)
        merged = merge_duplicate_investors(session, args.apply)

        if args.apply:
            session.commit()
            print(f"Applied data-quality repair: normalized={updated}, merged={merged}")
        else:
            session.rollback()
            print(f"Dry run only: would normalize={updated}, would merge={merged}")
            print("Run with --apply after reviewing the duplicate groups.")

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


if __name__ == "__main__":
    main()
