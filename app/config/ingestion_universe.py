from app.config.taxonomy import (
    CORE_SECTORS,
    INVESTMENT_STAGES,
    INVESTMENT_THEMES,
    INVESTOR_MARKETS,
    INVESTOR_SEARCH_TERMS,
)


SECTORS = CORE_SECTORS
STAGES = INVESTMENT_STAGES
GEOGRAPHIES = INVESTOR_MARKETS
THEMES = INVESTMENT_THEMES
INVESTOR_TERMS = INVESTOR_SEARCH_TERMS


def clean_query(query: str) -> str:
    return " ".join(query.split()).strip()


def _add_query(queries, query: str):
    query = clean_query(query)
    if len(query) > 10:
        queries.add(query)


def generate_sector_queries(queries):
    for sector in SECTORS:
        for term in INVESTOR_TERMS:
            _add_query(queries, f"{sector} {term}")


def generate_stage_queries(queries):
    for sector in SECTORS:
        for stage in STAGES:
            _add_query(queries, f"{sector} {stage} investors")
            _add_query(queries, f"{sector} {stage} venture capital")


def generate_geography_queries(queries):
    for sector in SECTORS:
        for geography in GEOGRAPHIES:
            _add_query(queries, f"{sector} investors in {geography}")
            _add_query(queries, f"{sector} venture capital firms in {geography}")
            _add_query(queries, f"{geography} {sector} startup investors")


def generate_theme_queries(queries):
    for theme in THEMES:
        _add_query(queries, f"{theme} investors")
        _add_query(queries, f"{theme} venture capital firms")
        _add_query(queries, f"{theme} startup investors")
        _add_query(queries, f"{theme} VC funds")


def generate_specialized_queries(queries):
    for sector in SECTORS:
        _add_query(queries, f"{sector} portfolio companies")
        _add_query(queries, f"{sector} investment thesis")
        _add_query(queries, f"{sector} startup ecosystem investors")
        _add_query(queries, f"{sector} startup funding firms")
        _add_query(queries, f"{sector} startup accelerators")
        _add_query(queries, f"{sector} startup investment platforms")


def generate_cross_theme_queries(queries):
    for sector in SECTORS:
        for theme in THEMES:
            _add_query(queries, f"{theme} {sector} investors")
            _add_query(queries, f"{theme} {sector} venture capital")


def generate_ingestion_queries():
    queries = set()
    generate_sector_queries(queries)
    generate_stage_queries(queries)
    generate_geography_queries(queries)
    generate_theme_queries(queries)
    generate_specialized_queries(queries)
    generate_cross_theme_queries(queries)
    return sorted(queries)


if __name__ == "__main__":
    for index, query in enumerate(generate_ingestion_queries()[:100], start=1):
        print(f"{index}. {query}")
