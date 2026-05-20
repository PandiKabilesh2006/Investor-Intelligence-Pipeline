from app.config.ingestion_universe import (
    QUERY_PATTERNS
)


def generate_queries(

    sector,

    stage,

    geography,

    theme=None
):

    queries = set()


    for pattern in QUERY_PATTERNS:

        try:

            query = pattern.format(

                sector=sector,

                stage=stage,

                geography=geography
            )


            queries.add(

                query.lower().strip()
            )

        except Exception:

            continue


    return list(queries)