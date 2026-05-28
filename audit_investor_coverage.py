import csv
import json
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy.orm import selectinload

from app.database.db import SessionLocal
from app.database.models import Investor
from app.utils.normalization import clean_list_values


COVERAGE_FIELDS = [
    "website",
    "focus_sectors",
    "investment_stage",
    "geography",
    "partners",
    "portfolio_companies",
    "contact_links",
]


def _partner_is_useful(partner):
    return bool(
        (partner.name or "").strip()
        or (partner.role or "").strip()
        or (partner.title or "").strip()
        or (partner.linkedin_url or "").strip()
        or (partner.twitter_url or "").strip()
    )


def _portfolio_company_is_useful(company):
    return bool((company.company_name or "").strip())


def compute_coverage_record(investor):
    website = bool((investor.website or "").strip())
    focus_sectors = clean_list_values(investor.focus_sectors or [])
    investment_stage = clean_list_values(investor.investment_stage or [])
    geography = clean_list_values(investor.geography or [])
    contact_links = clean_list_values(investor.contact_links or [])
    partners = [
        partner
        for partner in investor.partners or []
        if _partner_is_useful(partner)
    ]
    portfolio_companies = [
        company
        for company in investor.portfolio_companies or []
        if _portfolio_company_is_useful(company)
    ]

    flags = {
        "website": website,
        "focus_sectors": bool(focus_sectors),
        "investment_stage": bool(investment_stage),
        "geography": bool(geography),
        "partners": bool(partners),
        "portfolio_companies": bool(portfolio_companies),
        "contact_links": bool(contact_links),
    }

    score = sum(1 for value in flags.values() if value)
    missing_fields = [
        field
        for field in COVERAGE_FIELDS
        if not flags[field]
    ]

    if score >= 6:
        status = "strong"
    elif score >= 4:
        status = "usable"
    elif score >= 2:
        status = "thin"
    else:
        status = "critical"

    return {
        "investor_id": investor.id,
        "firm": investor.firm or "",
        "website": investor.website or "",
        "source_url": investor.source_url or "",
        "score": score,
        "max_score": len(COVERAGE_FIELDS),
        "status": status,
        "missing_fields": missing_fields,
        "focus_sectors": focus_sectors,
        "investment_stage": investment_stage,
        "geography": geography,
        "contact_links": contact_links,
        "partner_count": len(partners),
        "portfolio_company_count": len(portfolio_companies),
        "updated_at": investor.updated_at.isoformat() if investor.updated_at else None,
    }


def build_summary(records):
    summary = {
        "total_investors": len(records),
        "status_breakdown": dict(Counter(record["status"] for record in records)),
        "missing_field_breakdown": dict(
            Counter(
                field
                for record in records
                for field in record["missing_fields"]
            )
        ),
        "score_breakdown": dict(Counter(record["score"] for record in records)),
        "good_record_target": {
            "definition": "website + sector + stage + geography + at least one partner or portfolio company",
            "matching_records": sum(
                1
                for record in records
                if record["website"]
                and record["focus_sectors"]
                and record["investment_stage"]
                and record["geography"]
                and (
                    record["partner_count"] > 0
                    or record["portfolio_company_count"] > 0
                )
            ),
        },
    }

    if summary["total_investors"]:
        summary["average_score"] = round(
            sum(record["score"] for record in records) / summary["total_investors"],
            2,
        )
    else:
        summary["average_score"] = 0.0

    return summary


def export_csv(records, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "investor_id",
                "firm",
                "score",
                "max_score",
                "status",
                "missing_fields",
                "partner_count",
                "portfolio_company_count",
                "website",
                "source_url",
                "focus_sectors",
                "investment_stage",
                "geography",
                "contact_links",
                "updated_at",
            ]
        )

        for record in records:
            writer.writerow(
                [
                    record["investor_id"],
                    record["firm"],
                    record["score"],
                    record["max_score"],
                    record["status"],
                    "; ".join(record["missing_fields"]),
                    record["partner_count"],
                    record["portfolio_company_count"],
                    record["website"],
                    record["source_url"],
                    "; ".join(record["focus_sectors"]),
                    "; ".join(record["investment_stage"]),
                    "; ".join(record["geography"]),
                    "; ".join(record["contact_links"]),
                    record["updated_at"],
                ]
            )


def audit_investor_coverage(output_path):
    session = SessionLocal()

    try:
        investors = (
            session.query(Investor)
            .options(
                selectinload(Investor.partners),
                selectinload(Investor.portfolio_companies),
            )
            .order_by(Investor.firm.asc())
            .all()
        )

        records = [
            compute_coverage_record(investor)
            for investor in investors
            if investor.firm
        ]
    finally:
        session.close()

    summary = build_summary(records)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "summary": summary,
                "records": records,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    export_csv(
        records,
        output_path.with_suffix(".csv"),
    )

    print(f"Coverage audit exported to {output_path}")
    print(f"Total investors: {summary['total_investors']}")
    print(f"Average score: {summary['average_score']}/{len(COVERAGE_FIELDS)}")
    print(f"Status breakdown: {summary['status_breakdown']}")
    print(
        "Good record target matches: "
        f"{summary['good_record_target']['matching_records']}"
    )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        path = Path("exports/investor_coverage_audit.json")

    audit_investor_coverage(path)
