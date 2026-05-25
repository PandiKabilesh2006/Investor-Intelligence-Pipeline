import json

from app.database.db import SessionLocal

from app.database.models import Investor

from app.embeddings.embedder import (
    generate_investor_embedding
)


session = SessionLocal()


investors = session.query(Investor).all()


print(

    f"\nFound {len(investors)} investors\n"
)


updated = 0


for investor in investors:

    try:

        # =========================================
        # SKIP EXISTING EMBEDDINGS
        # =========================================

        if investor.embedding is not None:

            continue


        investor_data = {

            "firm": investor.firm,

            "focus_sectors": investor.focus_sectors or [],

            "investment_stage": investor.investment_stage or [],

            "geography": investor.geography or []
        }


        embedding = (

            generate_investor_embedding(

                investor_data
            )
        )


        investor.embedding = embedding


        session.commit()


        updated += 1


        print(

            f"Generated embedding: "
            f"{investor.firm}"
        )


    except Exception as error:

        session.rollback()

        print(

            f"Embedding failed: "
            f"{error}"
        )


session.close()


print(

    f"\nUpdated embeddings: "
    f"{updated}\n"
)