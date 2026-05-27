import json
import sys
from pathlib import Path

from app.database.db import SessionLocal
from app.database.models import Investor


def serialize_partner(partner):
    return {
        "name": partner.name or "",
        "role": partner.role or "",
        "linkedin_url": partner.linkedin_url or "",
        "twitter_url": partner.twitter_url or "",
    }


def serialize_portfolio_company(company):
    return {
        "company_name": company.company_name or "",
        "sector": company.sector or "",
    }


def serialize_investor(investor):
    return {
        "firm": investor.firm or "",
        "website": investor.website or "",
        "source_url": investor.source_url or "",
        "focus_sectors": investor.focus_sectors or [],
        "investment_stage": investor.investment_stage or [],
        "geography": investor.geography or [],
        "contact_links": investor.contact_links or [],
        "partners": [
            serialize_partner(partner)
            for partner in investor.partners
        ],
        "portfolio_companies": [
            serialize_portfolio_company(company)
            for company in investor.portfolio_companies
        ],
    }


def export_investors(output_path):
    session = SessionLocal()

    try:
        investors = (
            session.query(Investor)
            .order_by(Investor.firm.asc())
            .all()
        )

        records = [
            serialize_investor(investor)
            for investor in investors
            if investor.firm
        ]

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_path.write_text(
            json.dumps(
                records,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        print(
            f"Exported {len(records)} investors to {output_path}"
        )

    finally:
        session.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        path = Path("exports/investors_export.json")

    export_investors(path)
