import json

from sqlalchemy import or_

from app.database.db import SessionLocal

from app.database.models import Investor


session = SessionLocal()


# =========================================
# USER INPUT
# =========================================

sector = input(

    "Enter sector: "
).strip()

stage = input(

    "Enter investment stage: "
).strip()

geography = input(

    "Enter geography: "
).strip()


print("\nSearching investors...\n")


# =========================================
# SEARCH DATABASE
# =========================================

investors = session.query(Investor).all()


matched_investors = []


for investor in investors:

    sectors = json.loads(

        investor.focus_sectors or "[]"
    )

    stages = json.loads(

        investor.investment_stage or "[]"
    )

    geographies = json.loads(

        investor.geography or "[]"
    )


    sector_match = (

        sector.lower()

        in

        " ".join(sectors).lower()
    )


    stage_match = (

        stage.lower()

        in

        " ".join(stages).lower()
    )


    geography_match = (

        geography.lower()

        in

        " ".join(geographies).lower()
    )


    if (

        sector_match
        and
        stage_match
        and
        geography_match
    ):

        matched_investors.append(

            {
                "firm": investor.firm_name,
                "website": investor.website,
                "focus_sectors": sectors,
                "investment_stage": stages,
                "geography": geographies
            }
        )


# =========================================
# DISPLAY RESULTS
# =========================================

print("=" * 80)

print(

    f"\nFound "
    f"{len(matched_investors)} investors\n"
)


for investor in matched_investors:

    print(json.dumps(

        investor,

        indent=4
    ))

    print("-" * 80)


session.close()