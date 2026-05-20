from app.search.semantic_search import (
    semantic_investor_search
)


query = input(

    "\nEnter investor search query: "
)


results = semantic_investor_search(

    query=query,

    limit=10
)


print("\nTop Semantic Matches:\n")


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

        f"Distance: "
        f"{investor['distance']}"
    )

    print()