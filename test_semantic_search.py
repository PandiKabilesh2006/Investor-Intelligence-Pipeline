from app.search.semantic_search import (
    semantic_investor_search
)


# =========================================
# USER INPUTS
# =========================================

query = input(

    "\nEnter investor search query: "
)


sector = input(

    "Filter by sector (optional): "
).strip()


stage = input(

    "Filter by stage (optional): "
).strip()


geography = input(

    "Filter by geography (optional): "
).strip()


# =========================================
# SEARCH
# =========================================

results = semantic_investor_search(

    query=query,

    sector=sector,

    stage=stage,

    geography=geography,

    limit=10
)


# =========================================
# DISPLAY RESULTS
# =========================================

print("\nTop Investor Matches:\n")


for investor in results:

    print("=" * 80)

    print(

        f"Firm: "
        f"{investor['firm_name']}"
    )

    print(

        f"Website: "
        f"{investor['website']}"
    )

    print(

        f"Sectors: "
        f"{investor['focus_sectors']}"
    )

    print(

        f"Stages: "
        f"{investor['investment_stage']}"
    )

    print(

        f"Geography: "
        f"{investor['geography']}"
    )

    print(

        f"Distance: "
        f"{investor['distance']}"
    )

    print()