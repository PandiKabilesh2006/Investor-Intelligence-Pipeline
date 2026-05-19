import json

from app.database.db import SessionLocal

from app.database.models import Investor


session = SessionLocal()


# =========================================
# USER INPUT
# =========================================

sector = input(

    "Enter startup sector: "
).strip()

stage = input(

    "Enter investment stage: "
).strip()

geography = input(

    "Enter geography: "
).strip()


print("\nRanking investors...\n")


# =========================================
# LOAD INVESTORS
# =========================================

investors = session.query(Investor).all()


ranked_investors = []


# =========================================
# INVESTOR SCORING
# =========================================

for investor in investors:

    score = 0


    sectors = json.loads(

        investor.focus_sectors or "[]"
    )

    stages = json.loads(

        investor.investment_stage or "[]"
    )

    geographies = json.loads(

        investor.geography or "[]"
    )


    # =========================================
    # SECTOR MATCH
    # =========================================

    if sector.lower() in " ".join(sectors).lower():

        score += 5


    # =========================================
    # STAGE MATCH
    # =========================================

    if stage.lower() in " ".join(stages).lower():

        score += 5


    # =========================================
    # GEOGRAPHY MATCH
    # =========================================

    if geography.lower() in " ".join(geographies).lower():

        score += 3


    # =========================================
    # SAVE MATCHED INVESTORS
    # =========================================

    if score > 0:

        ranked_investors.append(

            {
                "firm": investor.firm_name,
                "website": investor.website,
                "score": score,
                "focus_sectors": sectors,
                "investment_stage": stages,
                "geography": geographies
            }
        )


# =========================================
# SORT BY SCORE
# =========================================

ranked_investors = sorted(

    ranked_investors,

    key=lambda x: x["score"],

    reverse=True
)


# =========================================
# DISPLAY RESULTS
# =========================================

print("=" * 80)

print(

    f"\nTop Matching Investors\n"
)


for investor in ranked_investors[:10]:

    print(json.dumps(

        investor,
        indent=4
    ))

    print("-" * 80)


session.close()