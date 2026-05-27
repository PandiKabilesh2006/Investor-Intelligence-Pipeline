from app.config.ingestion_universe import (
    QUERY_PATTERNS,
    INVESTOR_TERMS
)


def generate_queries(

    sector,

    stage,

    geography,

    theme=None
):

    if theme is None:
        theme = sector

    queries = set()


    for pattern in QUERY_PATTERNS:

        try:
            if "{term}" in pattern:
                for term in INVESTOR_TERMS:
                    query = pattern.format(
                        sector=sector,
                        stage=stage,
                        geography=geography,
                        theme=theme,
                        term=term,
                    )
                    queries.add(query.lower().strip())
            else:
                query = pattern.format(
                    sector=sector,
                    stage=stage,
                    geography=geography,
                    theme=theme,
                )


                queries.add(

                    query.lower().strip()
                )

        except Exception:

            continue


    return list(queries)