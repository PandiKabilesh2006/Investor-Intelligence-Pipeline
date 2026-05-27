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

                source_url,

                updated_at,

                focus_sectors,

                investment_stage,

                geography,

                contact_links,

                embedding <=> CAST(
                    :query_embedding AS vector
                ) AS distance

            FROM investors

            {where_clause}
            {"AND" if where_clause else "WHERE"} embedding IS NOT NULL

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


        # =====================================
        # PROCESS RESULTS
        # =====================================

        for row in results:

            # =================================
            # SEMANTIC SCORE
            # =================================

            semantic_score = max(

                0.0,

                min(
                    1.0,
                    1 - float(row.distance)
                )
            )


            # =================================
            # HYBRID BOOSTS
            # =================================

            sector_boost = 0.0

            stage_boost = 0.0

            geography_boost = 0.0


            # =================================
            # SECTOR BOOST
            # =================================

            if (

                sector

                and

                row.focus_sectors

                and

                sector in row.focus_sectors
            ):

                sector_boost = 0.15


            # =================================
            # STAGE BOOST
            # =================================

            if (

                stage

                and

                row.investment_stage

                and

                stage in row.investment_stage
            ):

                stage_boost = 0.05


            # =================================
            # GEOGRAPHY BOOST
            # =================================

            if (

                geography

                and

                row.geography

                and

                geography in row.geography
            ):

                geography_boost = 0.10


            # =================================
            # FINAL HYBRID SCORE
            # =================================

            hybrid_score = (

                semantic_score

                +

                sector_boost

                +

                stage_boost

                +

                geography_boost
            )


            # =================================
            # STORE RESULT
            # =================================

            investors.append({

                "id": row.id,

                "firm": row.firm,

                "firm_name": row.firm,

                "website": row.website,

                "source_url": row.source_url,

                "updated_at": row.updated_at,

                "focus_sectors": row.focus_sectors,

                "investment_stage": row.investment_stage,

                "geography": row.geography,

                "contact_links": row.contact_links,

                "distance": float(
                    row.distance
                ),

                "semantic_score": round(
                    semantic_score,
                    4
                ),

                "hybrid_score": round(
                    hybrid_score,
                    4
                ),

                "sector_boost": sector_boost,

                "stage_boost": stage_boost,

                "geography_boost": geography_boost
            })


        # =====================================
        # SORT BY HYBRID SCORE
        # =====================================

        investors = sorted(

            investors,

            key=lambda x: x["hybrid_score"],

            reverse=True
        )


        return investors


    finally:

        session.close()
