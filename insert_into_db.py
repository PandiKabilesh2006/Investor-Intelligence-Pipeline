import os
import json

from datetime import datetime, timezone

import psycopg2

from sentence_transformers import (
    SentenceTransformer
)

from pgvector.psycopg2 import (
    register_vector
)

from app.config.settings import (
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
)


# =========================================
# LAZY-LOAD EMBEDDING MODEL
# =========================================

embedding_model = None

def get_embedding_model():
    global embedding_model
    if embedding_model is None:
        embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return embedding_model


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
# INSERT SINGLE INVESTOR DATA
# =========================================

def insert_investor_data(data, conn=None):

    """
    Insert or update a single investor record (and its relational partner/portfolio company data) into the database.
    If conn is not provided, it creates a new database connection and commits/closes it.
    """

    should_close_conn = False

    if conn is None:

        conn = psycopg2.connect(

            host=DB_HOST,

            port=DB_PORT,

            database=DB_NAME,

            user=DB_USER,

            password=DB_PASSWORD
        )

        register_vector(conn)

        should_close_conn = True


    cursor = conn.cursor()

    try:

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

            print("Skipping (missing firm)")

            return False


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

        model = get_embedding_model()

        embedding = model.encode(

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

                    datetime.now(timezone.utc),

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

                    datetime.now(timezone.utc)
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


        if should_close_conn:

            conn.commit()


        return True


    except Exception as insertion_error:

        conn.rollback()

        print(

            f"Failed processing investor data: "
            f"{insertion_error}"
        )

        raise insertion_error


    finally:

        cursor.close()

        if should_close_conn:

            conn.close()


# =========================================
# MAIN FUNCTION
# =========================================

def main():

    # =========================================
    # DATABASE CONNECTION
    # =========================================

    conn = psycopg2.connect(

        host=DB_HOST,

        port=DB_PORT,

        database=DB_NAME,

        user=DB_USER,

        password=DB_PASSWORD
    )


    register_vector(conn)


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


        try:

            with open(

                file_path,

                "r",

                encoding="utf-8"
            ) as file:

                data = json.load(file)


            insert_investor_data(data, conn=conn)


        except Exception as file_error:

            conn.rollback()

            print(

                f"Failed processing "
                f"{file_name}: "
                f"{file_error}"
            )


    # =========================================
    # SAVE CHANGES
    # =========================================

    conn.commit()


    # =========================================
    # CLOSE CONNECTION
    # =========================================

    conn.close()


    print(

        "\nDatabase insertion complete.\n"
    )


if __name__ == "__main__":

    main()