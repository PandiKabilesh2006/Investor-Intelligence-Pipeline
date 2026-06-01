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
        _add_query(queries, f"{sector} venture capital firm portfolio")
        _add_query(queries, f"{sector} VC firm team portfolio")
        _add_query(queries, f"{sector} venture fund partners portfolio")
        _add_query(queries, f"{sector} VC fund investment thesis")


def generate_stage_queries(queries):
    for sector in SECTORS:
        for stage in STAGES:
            _add_query(queries, f"{sector} {stage} venture capital firm portfolio")
            _add_query(queries, f"{sector} {stage} VC firm team portfolio")
            _add_query(queries, f"{sector} {stage} venture fund partners")


def generate_geography_queries(queries):
    for sector in SECTORS:
        for geography in GEOGRAPHIES:
            if geography == "Global":
                continue

            _add_query(queries, f"{sector} venture capital firm portfolio in {geography}")
            _add_query(queries, f"{sector} VC firm team portfolio in {geography}")
            _add_query(queries, f"{geography} {sector} venture fund partners")


def generate_theme_queries(queries):
    for theme in THEMES:
        _add_query(queries, f"{theme} venture capital firm portfolio")
        _add_query(queries, f"{theme} VC firm team portfolio")
        _add_query(queries, f"{theme} venture fund partners portfolio")
        _add_query(queries, f"{theme} VC fund investment thesis")


def generate_specialized_queries(queries):
    for sector in SECTORS:
        _add_query(queries, f"{sector} venture fund portfolio companies")
        _add_query(queries, f"{sector} VC fund focus sectors portfolio")
        _add_query(queries, f"{sector} early stage fund investment thesis")
        _add_query(queries, f"{sector} venture capital investment team")


def generate_cross_theme_queries(queries):
    for sector in SECTORS:
        for theme in THEMES:
            _add_query(queries, f"{theme} {sector} venture capital firm portfolio")
            _add_query(queries, f"{theme} {sector} VC fund partners")


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
