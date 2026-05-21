# =========================================
# INVESTOR INGESTION UNIVERSE
# =========================================
# Production-Grade Investor Discovery
# Query Generation System
#
# Purpose:
# Generate high-signal investor discovery
# queries for continuous ecosystem ingestion.
#
# Design Goals:
# - scalable
# - maintainable
# - ontology-driven
# - low-noise
# - production-ready
#
# =========================================


# =========================================
# CORE SECTORS
# =========================================

SECTORS = [

    "Artificial Intelligence",

    "B2B",

    "SaaS",

    "Voice AI"
]


# =========================================
# INVESTMENT STAGES
# =========================================

STAGES = [

    "Pre-Seed",

    "Seed",

    "Series A",

    "Series B",

    "Growth Stage"
]


# =========================================
# GEOGRAPHIES
# =========================================

GEOGRAPHIES = [

    "United States",

    "India",

    "Europe",

    "Southeast Asia",

    "Middle East",

    "Global"
]


# =========================================
# INVESTMENT THEMES
# =========================================

THEMES = [

    "AI infrastructure",

    "Enterprise Software",

    "Developer Tools",

    "Workflow Automation",

    "Vertical AI",

    "Voice Agents",

    "Machine Learning",

    "Automation"
]


# =========================================
# HIGH-SIGNAL INVESTOR TERMS
# =========================================

INVESTOR_TERMS = [

    "venture capital firms",

    "startup investors",

    "VC funds",

    "venture capital",

    "angel investors",

    "early-stage investors",

    "seed investors",

    "Series A investors",

    "institutional investors",

    "technology investors"
]


# =========================================
# QUERY CLEANER
# =========================================

def clean_query(query: str) -> str:

    """
    Normalize search query formatting.
    """

    return " ".join(

        query.split()

    ).strip()


# =========================================
# QUERY STORAGE
# =========================================

generated_queries = set()


# =========================================
# ADD QUERY
# =========================================

def add_query(query: str):

    """
    Add cleaned unique query.
    """

    query = clean_query(query)


    if len(query) > 10:

        generated_queries.add(query)


# =========================================
# SECTOR QUERIES
# =========================================

def generate_sector_queries():

    for sector in SECTORS:

        for term in INVESTOR_TERMS:

            add_query(

                f"{sector} {term}"
            )


# =========================================
# SECTOR + STAGE
# =========================================

def generate_stage_queries():

    for sector in SECTORS:

        for stage in STAGES:

            add_query(

                f"{sector} {stage} investors"
            )

            add_query(

                f"{sector} {stage} venture capital"
            )


# =========================================
# SECTOR + GEOGRAPHY
# =========================================

def generate_geography_queries():

    for sector in SECTORS:

        for geography in GEOGRAPHIES:

            add_query(

                f"{sector} investors in {geography}"
            )

            add_query(

                f"{sector} venture capital firms in {geography}"
            )

            add_query(

                f"{geography} {sector} startup investors"
            )


# =========================================
# THEME QUERIES
# =========================================

def generate_theme_queries():

    for theme in THEMES:

        add_query(

            f"{theme} investors"
        )

        add_query(

            f"{theme} venture capital firms"
        )

        add_query(

            f"{theme} startup investors"
        )

        add_query(

            f"{theme} VC funds"
        )


# =========================================
# SPECIALIZED DISCOVERY
# =========================================

def generate_specialized_queries():

    for sector in SECTORS:

        add_query(

            f"{sector} portfolio companies"
        )

        add_query(

            f"{sector} investment thesis"
        )

        add_query(

            f"{sector} startup ecosystem investors"
        )

        add_query(

            f"{sector} startup funding firms"
        )

        add_query(

            f"{sector} startup accelerators"
        )

        add_query(

            f"{sector} startup investment platforms"
        )


# =========================================
# CROSS-THEME DISCOVERY
# =========================================

def generate_cross_theme_queries():

    for sector in SECTORS:

        for theme in THEMES:

            add_query(

                f"{theme} {sector} investors"
            )

            add_query(

                f"{theme} {sector} venture capital"
            )


# =========================================
# MAIN QUERY GENERATOR
# =========================================

def generate_ingestion_queries():

    """
    Generate high-signal investor
    discovery queries.
    """

    generate_sector_queries()

    generate_stage_queries()

    generate_geography_queries()

    generate_theme_queries()

    generate_specialized_queries()

    generate_cross_theme_queries()


    return sorted(

        list(generated_queries)
    )


# =========================================
# MAIN EXECUTION
# =========================================

if __name__ == "__main__":

    queries = generate_ingestion_queries()


    print("\n" + "=" * 80)

    print("\nInvestor Intelligence Query Universe\n")

    print(

        f"Total Queries Generated: "
        f"{len(queries)}\n"
    )


    # =====================================
    # DISPLAY SAMPLE QUERIES
    # =====================================

    for index, query in enumerate(

        queries[:100],

        start=1
    ):

        print(

            f"{index}. {query}"
        )


    print(

        "\nQuery generation completed.\n"
    )

    print("=" * 80)