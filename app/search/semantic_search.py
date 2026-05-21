from sqlalchemy import text

from app.database.db import SessionLocal

from app.embeddings.embedder import (
    embedding_model
)


# =========================================
# SEMANTIC INVESTOR SEARCH
# =========================================

def semantic_investor_search(

    query,

    sector=None,

    stage=None,

    geography=None,

    limit=10
):

    session = SessionLocal()


    try:

        # =====================================
        # GENERATE QUERY EMBEDDING
        # =====================================

        query_embedding = (

            embedding_model.encode(
                query
            ).tolist()
        )


        query_embedding = (

            "["
            +
            ",".join(
                map(str, query_embedding)
            )
            +
            "]"
        )


        # =====================================
        # DYNAMIC FILTERS
        # =====================================

        filters = []


        params = {

            "query_embedding": query_embedding,

            "limit": limit
        }


        # =====================================
        # SECTOR FILTER
        # =====================================

        if sector:

            filters.append(

                ":sector = ANY(focus_sectors)"
            )

            params["sector"] = sector


        # =====================================
        # STAGE FILTER
        # =====================================

        if stage:

            filters.append(

                ":stage = ANY(investment_stage)"
            )

            params["stage"] = stage


        # =====================================
        # GEOGRAPHY FILTER
        # =====================================

        if geography:

            filters.append(

                ":geography = ANY(geography)"
            )

            params["geography"] = geography


        # =====================================
        # BUILD WHERE CLAUSE
        # =====================================

        where_clause = ""


        if filters:

            where_clause = (

                "WHERE "
                +
                " AND ".join(filters)
            )


        # =====================================
        # VECTOR SEARCH SQL
        # =====================================

        sql = text(

            f"""
            SELECT

                id,

                firm,

                website,

                focus_sectors,

                investment_stage,

                geography,

                contact_links,

                embedding <=> CAST(
                    :query_embedding AS vector
                ) AS distance

            FROM investors

            {where_clause}

            ORDER BY embedding <=> CAST(
                :query_embedding AS vector
            )

            LIMIT :limit
            """
        )


        results = session.execute(

            sql,

            params
        )


        investors = []


        for row in results:

            investors.append({

                "id": row.id,

                "firm_name": row.firm,

                "website": row.website,

                "focus_sectors": row.focus_sectors,

                "investment_stage": row.investment_stage,

                "geography": row.geography,

                "contact_links": row.contact_links,

                "distance": float(

                    row.distance
                )
            })


        return investors


    finally:

        session.close()