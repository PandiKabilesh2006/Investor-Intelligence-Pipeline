import os
import json

import psycopg2

from sentence_transformers import (
    SentenceTransformer
)

from pgvector.psycopg2 import register_vector


# =========================================
# DATABASE CONNECTION
# =========================================

conn = psycopg2.connect(

    host="localhost",

    database="investor_intelligence",

    user="postgres",

    password="LiveClass2270157"
)


register_vector(conn)

cursor = conn.cursor()


# =========================================
# EMBEDDING MODEL
# =========================================

embedding_model = SentenceTransformer(

    "all-MiniLM-L6-v2"
)


# =========================================
# PARSED JSON FOLDER
# =========================================

PARSED_FOLDER = "parsed_json"


# =========================================
# LOAD JSON FILES
# =========================================

json_files = [

    file

    for file in os.listdir(PARSED_FOLDER)

    if file.endswith(".json")
]


print(

    f"\nFound {len(json_files)} parsed files\n"
)


# =========================================
# INSERT LOOP
# =========================================

for file_name in json_files:

    file_path = os.path.join(

        PARSED_FOLDER,

        file_name
    )


    with open(

        file_path,

        "r",

        encoding="utf-8"
    ) as file:

        data = json.load(file)


    # =====================================
    # REQUIRED FIELDS
    # =====================================

    firm = data.get(

        "firm",

        ""
    ).strip()


    if not firm:

        print(

            f"Skipping {file_name} "
            f"(missing firm)"
        )

        continue


    website = data.get(

        "website",

        ""
    ).strip()


    focus_sectors = data.get(

        "focus_sectors",

        []
    )


    investment_stage = data.get(

        "investment_stage",

        []
    )


    geography = data.get(

        "geography",

        []
    )


    contact_links = data.get(

        "contact_links",

        []
    )


    partners = data.get(

        "partners",

        []
    )


    portfolio_companies = data.get(

        "portfolio_companies",

        []
    )


    # =====================================
    # EMBEDDING TEXT
    # =====================================

    embedding_text = " ".join([

        firm,

        website,

        " ".join(focus_sectors),

        " ".join(investment_stage),

        " ".join(geography),

        " ".join(partners),

        " ".join(portfolio_companies)
    ])


    embedding = embedding_model.encode(

        embedding_text
    ).tolist()


    # =====================================
    # CHECK DUPLICATE
    # =====================================

    cursor.execute(

        """
        SELECT id
        FROM investors
        WHERE LOWER(firm) = LOWER(%s)
        """,

        (firm,)
    )


    existing = cursor.fetchone()


    # =====================================
    # UPDATE EXISTING INVESTOR
    # =====================================

    if existing:

        investor_id = existing[0]


        cursor.execute(

            """
            UPDATE investors
            SET

                website = %s,

                focus_sectors = %s,

                investment_stage = %s,

                geography = %s,

                contact_links = %s,

                embedding = %s

            WHERE id = %s
            """,

            (

                website,

                focus_sectors,

                investment_stage,

                geography,

                contact_links,

                embedding,

                investor_id
            )
        )


        print(

            f"Updated investor: {firm}"
        )


    # =====================================
    # INSERT NEW INVESTOR
    # =====================================

    else:

        cursor.execute(

            """
            INSERT INTO investors (

                firm,

                website,

                focus_sectors,

                investment_stage,

                geography,

                contact_links,

                embedding

            )

            VALUES (

                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )

            RETURNING id
            """,

            (

                firm,

                website,

                focus_sectors,

                investment_stage,

                geography,

                contact_links,

                embedding
            )
        )


        investor_id = cursor.fetchone()[0]


        print(

            f"Inserted investor: {firm}"
        )


    # =====================================
    # DELETE OLD RELATIONAL DATA
    # =====================================

    cursor.execute(

        """
        DELETE FROM partners
        WHERE investor_id = %s
        """,

        (investor_id,)
    )


    cursor.execute(

        """
        DELETE FROM portfolio_companies
        WHERE investor_id = %s
        """,

        (investor_id,)
    )


    # =====================================
    # INSERT PARTNERS
    # =====================================

    for partner in partners:

        cursor.execute(

            """
            INSERT INTO partners (

                investor_id,

                name

            )

            VALUES (

                %s,
                %s
            )
            """,

            (

                investor_id,

                partner
            )
        )


    # =====================================
    # INSERT PORTFOLIO COMPANIES
    # =====================================

    for company in portfolio_companies:

        cursor.execute(

            """
            INSERT INTO portfolio_companies (

                investor_id,

                company_name

            )

            VALUES (

                %s,
                %s
            )
            """,

            (

                investor_id,

                company
            )
        )


# =========================================
# SAVE CHANGES
# =========================================

conn.commit()


# =========================================
# CLOSE CONNECTION
# =========================================

cursor.close()

conn.close()


print(

    "\nDatabase insertion complete.\n"
)