import os
import json

from datetime import datetime

import psycopg2

from sentence_transformers import (
    SentenceTransformer
)

from pgvector.psycopg2 import (
    register_vector
)


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
# SAFE LIST NORMALIZATION
# =========================================

def ensure_list(value):

    """
    Normalize field into proper list format.
    Prevents character-separated corruption.
    """

    if value is None:

        return []


    # =====================================
    # ALREADY A LIST
    # =====================================

    if isinstance(value, list):

        cleaned = []

        for item in value:

            if item is None:

                continue

            item = str(item).strip()

            if item:

                cleaned.append(item)

        return cleaned


    # =====================================
    # STRING → SINGLE ITEM LIST
    # =====================================

    if isinstance(value, str):

        value = value.strip()

        if not value:

            return []

        return [value]


    # =====================================
    # FALLBACK
    # =====================================

    return []


# =========================================
# INSERT LOOP
# =========================================

for file_name in json_files:

    file_path = os.path.join(

        PARSED_FOLDER,

        file_name
    )


    try:

        with open(

            file_path,

            "r",

            encoding="utf-8"
        ) as file:

            data = json.load(file)


        # =====================================
        # REQUIRED FIELDS
        # =====================================

        firm = str(

            data.get(

                "firm",

                ""
            )

        ).strip()


        if not firm:

            print(

                f"Skipping {file_name} "
                f"(missing firm)"
            )

            continue


        website = str(

            data.get(

                "website",

                ""
            )

        ).strip()


        source_url = str(

            data.get(

                "source_url",

                ""
            )

        ).strip()


        # =====================================
        # SAFE NORMALIZATION
        # =====================================

        focus_sectors = ensure_list(

            data.get(

                "focus_sectors",

                []
            )
        )


        investment_stage = ensure_list(

            data.get(

                "investment_stage",

                []
            )
        )


        geography = ensure_list(

            data.get(

                "geography",

                []
            )
        )


        contact_links = ensure_list(

            data.get(

                "contact_links",

                []
            )
        )


        partners = ensure_list(

            data.get(

                "partners",

                []
            )
        )


        portfolio_companies = ensure_list(

            data.get(

                "portfolio_companies",

                []
            )
        )


        # =====================================
        # EMBEDDING TEXT
        # =====================================

        embedding_text = " ".join([

            firm,

            website,

            source_url,

            " ".join(focus_sectors),

            " ".join(investment_stage),

            " ".join(geography),

            " ".join(contact_links),

            " ".join(partners),

            " ".join(portfolio_companies)
        ])


        # =====================================
        # GENERATE EMBEDDING
        # =====================================

        embedding = embedding_model.encode(

            embedding_text
        ).tolist()


        # =====================================
        # DUPLICATE CHECK
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

                    source_url = %s,

                    focus_sectors = %s,

                    investment_stage = %s,

                    geography = %s,

                    contact_links = %s,

                    embedding = %s,

                    updated_at = %s

                WHERE id = %s
                """,

                (

                    website,

                    source_url,

                    focus_sectors,

                    investment_stage,

                    geography,

                    contact_links,

                    embedding,

                    datetime.utcnow(),

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

                    source_url,

                    focus_sectors,

                    investment_stage,

                    geography,

                    contact_links,

                    embedding,

                    updated_at

                )

                VALUES (

                    %s,
                    %s,
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

                    source_url,

                    focus_sectors,

                    investment_stage,

                    geography,

                    contact_links,

                    embedding,

                    datetime.utcnow()
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


    except Exception as insertion_error:

        print(

            f"Failed processing "
            f"{file_name}: "
            f"{insertion_error}"
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