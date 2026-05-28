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
from app.utils.normalization import (
    merge_clean_lists,
    normalize_firm_key,
    normalize_geography,
    normalize_sector,
    normalize_stage,
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


def merge_record_lists(incoming, existing):
    return merge_clean_lists(
        existing or [],
        incoming or []
    )


def _merge_partner(existing, incoming):
    return {
        "name": incoming.get("name") or existing.get("name") or "",
        "role": incoming.get("role") or existing.get("role") or "",
        "title": incoming.get("title") or existing.get("title") or incoming.get("role") or existing.get("role") or "",
        "linkedin_url": incoming.get("linkedin_url") or existing.get("linkedin_url") or "",
        "twitter_url": incoming.get("twitter_url") or existing.get("twitter_url") or "",
        "source_url": incoming.get("source_url") or existing.get("source_url") or "",
        "extraction_confidence": max(
            float(existing.get("extraction_confidence") or 0.0),
            float(incoming.get("extraction_confidence") or 0.0),
        ),
    }


def _merge_company(existing, incoming):
    return {
        "company_name": incoming.get("company_name") or existing.get("company_name") or "",
        "sector": incoming.get("sector") or existing.get("sector") or "",
    }


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
        focus_sectors = normalize_sector(focus_sectors)


        investment_stage = ensure_list(

            data.get(

                "investment_stage",

                []
            )
        )
        investment_stage = normalize_stage(investment_stage)


        geography = ensure_list(

            data.get(

                "geography",

                []
            )
        )
        geography = normalize_geography(geography)


        contact_links = ensure_list(

            data.get(

                "contact_links",

                []
            )
        )
        contact_links = merge_clean_lists(contact_links)


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

        has_investor_evidence = any(
            [
                focus_sectors,
                investment_stage,
                geography,
                contact_links,
                partners,
                portfolio_companies,
            ]
        )

        if not has_investor_evidence:

            print(

                f"Skipping {firm}: no structured investor evidence extracted"
            )

            return False


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
            WHERE regexp_replace(
                regexp_replace(
                    LOWER(firm),
                    '\\m(the|llc|llp|ltd|limited|inc|incorporated|corp|corporation)\\M',
                    '',
                    'g'
                ),
                '[^a-z0-9]',
                '',
                'g'
            ) = %s
               OR LOWER(firm) = LOWER(%s)
               OR (website <> '' AND website = %s)
            """,

            (
                normalize_firm_key(firm),
                firm,
                website,
            )
        )


        existing = cursor.fetchone()


        # =====================================
        # UPDATE EXISTING INVESTOR
        # =====================================

        if existing:

            investor_id = existing[0]

            website = website or existing[1] or ""

            source_url = source_url or existing[2] or ""

            focus_sectors = normalize_sector(
                merge_record_lists(focus_sectors, existing[3])
            )

            investment_stage = normalize_stage(
                merge_record_lists(investment_stage, existing[4])
            )

            geography = normalize_geography(
                merge_record_lists(geography, existing[5])
            )

            contact_links = merge_record_lists(contact_links, existing[6])

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
        # UPSERT PARTNERS
        # =====================================

        if partners:

            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    role,
                    title,
                    linkedin_url,
                    twitter_url,
                    source_url,
                    extraction_confidence
                FROM partners
                WHERE investor_id = %s
                """,
                (investor_id,)
            )

            existing_partners = {
                str(row[1]).strip().lower(): {
                    "id": row[0],
                    "name": row[1] or "",
                    "role": row[2] or "",
                    "title": row[3] or "",
                    "linkedin_url": row[4] or "",
                    "twitter_url": row[5] or "",
                    "source_url": row[6] or "",
                    "extraction_confidence": row[7] or 0.0,
                }
                for row in cursor.fetchall()
                if str(row[1] or "").strip()
            }

            for partner in partners:
                partner_key = partner["name"].strip().lower()
                existing_partner = existing_partners.get(partner_key)
                merged_partner = _merge_partner(existing_partner or {}, partner)

                if existing_partner:
                    cursor.execute(
                        """
                        UPDATE partners
                        SET
                            role = %s,
                            title = %s,
                            linkedin_url = %s,
                            twitter_url = %s,
                            source_url = %s,
                            extraction_confidence = %s,
                            scraped_at = %s,
                            updated_at = %s
                        WHERE id = %s
                        """,
                        (
                            merged_partner["role"],
                            merged_partner["title"],
                            merged_partner["linkedin_url"],
                            merged_partner["twitter_url"],
                            merged_partner["source_url"],
                            merged_partner["extraction_confidence"],
                            datetime.now(timezone.utc),
                            datetime.now(timezone.utc),
                            existing_partner["id"],
                        )
                    )
                else:
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
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            investor_id,
                            merged_partner["name"],
                            merged_partner["role"],
                            merged_partner["title"],
                            merged_partner["linkedin_url"],
                            merged_partner["twitter_url"],
                            merged_partner["source_url"],
                            merged_partner["extraction_confidence"],
                            datetime.now(timezone.utc),
                        )
                    )

        # =====================================
        # UPSERT PORTFOLIO COMPANIES
        # =====================================

        if portfolio_companies:

            cursor.execute(
                """
                SELECT
                    id,
                    company_name,
                    sector
                FROM portfolio_companies
                WHERE investor_id = %s
                """,
                (investor_id,)
            )

            existing_companies = {
                str(row[1]).strip().lower(): {
                    "id": row[0],
                    "company_name": row[1] or "",
                    "sector": row[2] or "",
                }
                for row in cursor.fetchall()
                if str(row[1] or "").strip()
            }

            for company in portfolio_companies:
                company_key = company["company_name"].strip().lower()
                existing_company = existing_companies.get(company_key)
                merged_company = _merge_company(existing_company or {}, company)

                if existing_company:
                    cursor.execute(
                        """
                        UPDATE portfolio_companies
                        SET sector = %s
                        WHERE id = %s
                        """,
                        (
                            merged_company["sector"],
                            existing_company["id"],
                        )
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO portfolio_companies (
                            investor_id,
                            company_name,
                            sector
                        )
                        VALUES (%s, %s, %s)
                        """,
                        (
                            investor_id,
                            merged_company["company_name"],
                            merged_company["sector"],
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
