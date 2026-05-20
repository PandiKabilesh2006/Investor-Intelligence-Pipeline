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

    limit=10
):

    session = SessionLocal()


    try:

        # =========================================
        # GENERATE QUERY EMBEDDING
        # =========================================

        query_embedding = (

            embedding_model.encode(

                query
            ).tolist()
        )
        query_embedding=(
            "["
            +
            ",".join(
                map(str,query_embedding)
            )
            +
            "]"
        )


        # =========================================
        # VECTOR SIMILARITY SEARCH
        # =========================================

        sql = text(

            """
            SELECT
                id,
                firm_name,
                website,
                focus_sectors,
                investment_stage,
                geography,
                embedding <=> CAST(:query_embedding AS vector)
                    AS distance

            FROM investors

            ORDER BY embedding <=> CAST(:query_embedding AS vector)

            LIMIT :limit
            """
        )


        results = session.execute(

            sql,

            {

                "query_embedding": query_embedding,

                "limit": limit
            }
        )


        investors = []


        for row in results:

            investors.append({

                "id": row.id,

                "firm_name": row.firm_name,

                "website": row.website,

                "focus_sectors": row.focus_sectors,

                "investment_stage": row.investment_stage,

                "geography": row.geography,

                "distance": float(

                    row.distance
                )
            })


        return investors


    finally:

        session.close()