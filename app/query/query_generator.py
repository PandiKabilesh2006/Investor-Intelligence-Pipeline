from app.config.ingestion_universe import (

    generate_ingestion_queries
)


# =========================================
# QUERY GENERATOR
# =========================================

def generate_queries(

    sector=None,

    stage=None,

    geography=None,

    theme=None
):

    """
    Production-grade query generator.

    Returns dynamically generated
    investor discovery queries.
    """

    queries = generate_ingestion_queries()


    # =====================================
    # OPTIONAL FILTERING
    # =====================================

    filtered_queries = []


    for query in queries:

        query_lower = query.lower()


        if sector:

            if sector.lower() not in query_lower:

                continue


        if stage:

            if stage.lower() not in query_lower:

                continue


        if geography:

            if geography.lower() not in query_lower:

                continue


        if theme:

            if theme.lower() not in query_lower:

                continue


        filtered_queries.append(query)


    # =====================================
    # FALLBACK
    # =====================================

    if len(filtered_queries) == 0:

        return queries


    return filtered_queries