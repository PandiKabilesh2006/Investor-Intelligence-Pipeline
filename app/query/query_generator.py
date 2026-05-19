#multi-query retrieval coverage
def generate_queries(

    sector,
    stage,
    geography,
    theme
):

    queries = [

        # Core investor searches
        f"{sector} investors",

        f"{sector} venture capital firms",

        f"{sector} startup investors",

        # Stage-focused
        f"{sector} {stage} investors",

        f"{sector} {stage} VC firms",

        # Geography-focused
        f"{sector} investors in {geography}",

        f"{sector} venture capital firms in {geography}",

        # Theme-focused
        f"{theme} investors",

        f"{theme} venture capital firms",

        f"{sector} {theme} investors",

        # Portfolio/thesis discovery
        f"{sector} investment thesis",

        f"{sector} portfolio companies",

        f"{sector} investment firms",

        f"{sector} AI startup investors",

        f"{sector} emerging VC firms",

        # Alternative terminology
        f"{sector} startup funds",

        f"{sector} early-stage investors",

        f"{sector} growth investors",

        f"{sector} enterprise software investors"
    ]


    # =========================================
    # DEDUPLICATION
    # =========================================

    queries = list(

        set(query.strip() for query in queries)
    )


    return queries