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

            if isinstance(item, dict):

                cleaned.append(item)

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


def normalize_partner_records(value):

    partners = []

    for item in ensure_list(value):

        if isinstance(item, dict):

            try:
                extraction_confidence = float(
                    item.get("extraction_confidence", 0.0) or 0.0
                )
            except (TypeError, ValueError):
                extraction_confidence = 0.0

            partner = {

                "name": str(
                    item.get("name", "")
                ).strip(),

                "role": str(
                    item.get("role", "")
                ).strip(),

                "title": str(
                    item.get("title", item.get("role", ""))
                ).strip(),

                "linkedin_url": str(
                    item.get("linkedin_url", "")
                ).strip(),

                "twitter_url": str(
                    item.get("twitter_url", "")
                ).strip(),

                "source_url": str(
                    item.get(
                        "source_url",
                        item.get("linkedin_url", "")
                    )
                ).strip(),

                "extraction_confidence": extraction_confidence
            }

        else:

            partner = {

                "name": str(item).strip(),

                "role": "",

                "title": "",

                "linkedin_url": "",

                "twitter_url": "",

                "source_url": "",

                "extraction_confidence": 0.0
            }

        if partner["name"]:

            partners.append(partner)

    unique = {}

    for partner in partners:

        unique.setdefault(

            partner["name"].lower(),

            partner
        )

    return list(

        unique.values()
    )


def normalize_portfolio_company_records(value):

    companies = []

    for item in ensure_list(value):

        if isinstance(item, dict):

            company = {

                "company_name": str(
                    item.get("company_name", "")
                    or
                    item.get("name", "")
                ).strip(),

                "sector": str(
                    item.get("sector", "")
                ).strip()
            }

        else:

            company = {

                "company_name": str(item).strip(),

                "sector": ""
            }

        if company["company_name"]:

            companies.append(company)

    unique = {}

    for company in companies:

        unique.setdefault(

            company["company_name"].lower(),

            company
        )

    return list(

        unique.values()
    )


def build_embedding_text(

    firm,

    website,

    source_url,

    focus_sectors,

    investment_stage,

    geography,

    contact_links,

    partners,

    portfolio_companies
):

    return " ".join([

        firm,

        website,

        source_url,

        " ".join(focus_sectors),

        " ".join(investment_stage),

        " ".join(geography),

        " ".join(contact_links),

        " ".join(
            [
                " ".join(
                    [
                        partner["name"],
                        partner["role"],
                        partner["linkedin_url"],
                        partner["twitter_url"]
                    ]
                )
                for partner in partners
            ]
        ),

        " ".join(
            [
                " ".join(
                    [
                        company["company_name"],
                        company["sector"]
                    ]
                )
                for company in portfolio_companies
            ]
        )
    ])


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


        partners = normalize_partner_records(

            data.get(

                "partners",

                []
            )
        )


        portfolio_companies = normalize_portfolio_company_records(

            data.get(

                "portfolio_companies",

                []
            )
        )


        # =====================================
        # EMBEDDING TEXT
        # =====================================

        embedding_text = build_embedding_text(

            firm,

            website,

            source_url,

            focus_sectors,

            investment_stage,

            geography,

            contact_links,

            partners,

            portfolio_companies
        )


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
            SELECT
                id,
                website,
                source_url,
                focus_sectors,
                investment_stage,
                geography,
                contact_links
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

            website = website or existing[1] or ""

            source_url = source_url or existing[2] or ""

            focus_sectors = focus_sectors or existing[3] or []

            investment_stage = investment_stage or existing[4] or []

            geography = geography or existing[5] or []

            contact_links = contact_links or existing[6] or []

            embedding_text = build_embedding_text(

                firm,

                website,

                source_url,

                focus_sectors,

                investment_stage,

                geography,

                contact_links,

                partners,

                portfolio_companies
            )

            embedding = model.encode(

                embedding_text
            ).tolist()


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
        # INSERT PARTNERS
        # =====================================

        if partners:

            cursor.execute(

                """
                DELETE FROM partners
                WHERE investor_id = %s
                """,

                (investor_id,)
            )


        for partner in partners:

            cursor.execute(

                """
                INSERT INTO partners (

                    investor_id,

                    name,

                    role,

                    title,

                    linkedin_url,

                    twitter_url,

                    source_url,

                    extraction_confidence,

                    scraped_at

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
                """,

                (

                    investor_id,

                    partner["name"],

                    partner["role"],

                    partner["title"],

                    partner["linkedin_url"],

                    partner["twitter_url"],

                    partner["source_url"],

                    partner["extraction_confidence"],

                    datetime.now(timezone.utc)
                )
            )


        # =====================================
        # INSERT PORTFOLIO COMPANIES
        # =====================================

        if portfolio_companies:

            cursor.execute(

                """
                DELETE FROM portfolio_companies
                WHERE investor_id = %s
                """,

                (investor_id,)
            )


        for company in portfolio_companies:

            cursor.execute(

                """
                INSERT INTO portfolio_companies (

                    investor_id,

                    company_name,

                    sector

                )

                VALUES (

                    %s,
                    %s,
                    %s
                )
                """,

                (

                    investor_id,

                    company["company_name"],

                    company["sector"]
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
    # PARSED JSON FOLDER
    # =========================================

    PARSED_FOLDER = "parsed_json"


    # =========================================
    # LOAD JSON FILES
    # =========================================

    json_files = [

        file

        for file in os.listdir(PARSED_FOLDER)

        if (
            file.endswith(".json")
            and
            (
                not os.getenv("PIPELINE_RUN_STARTED_TS")
                or
                os.path.getmtime(
                    os.path.join(PARSED_FOLDER, file)
                )
                >=
                float(os.getenv("PIPELINE_RUN_STARTED_TS"))
            )
        )
    ]


    print(

        f"\nFound {len(json_files)} parsed files\n"
    )

    if not json_files:

        print("No parsed files to insert. Skipping database connection.\n")

        return

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
