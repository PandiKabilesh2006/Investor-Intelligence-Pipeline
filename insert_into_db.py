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

from app.config.settings import (
    DB_HOST,
    DB_PORT,
    DB_NAME,
    DB_USER,
    DB_PASSWORD,
    INGESTION_ALLOW_MOCK_DATA,
    INGESTION_REQUIRE_RAW_PROVENANCE,
    PARTNER_MIN_CONFIDENCE,
    PARTNER_ROLE_TITLES,
    PARSED_DATA_FOLDER,
    RAW_DATA_FOLDER,
)
from app.validation.investor_validation import (
    find_duplicate_investor_id,
    is_rejected_url,
    normalize_firm_name,
    validate_parsed_investor,
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
# FILTER FAKE/GENERIC PARTNER NAMES
# =========================================

import re as _re

# VC role titles and generic terms that are NOT person names
_ROLE_TITLES = {
    title.strip().lower()
    for title in PARTNER_ROLE_TITLES
}

def filter_real_partners(partners):

    """
    Remove LLM-hallucinated placeholder partner names.
    Keeps only real human names.

    Accepts:
    - Multi-word names: 'Marc Andreessen', 'Scott Dorsey'
    - Single-word mononyms >= 5 chars that are not role titles:
      'Aakrit', 'Pratyush'

    Rejects:
    - 'Partner 7', 'Partner N' numbered placeholders
    - Pure role titles like 'Managing Partner', 'Director'
    - Very short strings (< 4 chars)
    - Numbers-only or no-letter strings
    - Common non-person aggregator terms
    """

    real_partners = []

    for partner in partners:

        if isinstance(partner, dict):

            partner_record = partner.copy()

            name = str(partner_record.get("name", "")).strip()

        else:

            name = str(partner).strip()

            partner_record = {

                "name": name,

                "role": "",

                "linkedin_url": "",

                "twitter_url": "",

                "source_url": "",

                "confidence": 0.7
            }

        # Must be at least 4 characters
        if len(name) < 4:
            continue

        # Reject generic numbered placeholders: 'Partner 7'
        if _re.match(r'^Partner\s+\d+$', name, _re.IGNORECASE):
            continue

        # Reject pure role titles (exact match, case-insensitive)
        if name.lower() in _ROLE_TITLES:
            continue

        # Reject entries that are purely numeric
        if _re.match(r'^[\d\s]+$', name):
            continue

        # Reject entries with no letters at all
        if not _re.search(r'[a-zA-Z]', name):
            continue

        # Single-word names: allow only if >= 5 chars
        # (catches real mononyms like 'Aakrit', rejects 'LP', 'GP')
        words = name.split()
        if len(words) == 1 and len(name) < 5:
            continue

        try:
            confidence = float(partner_record.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0

        # LLM-parsed partners often omit confidence; treat validated names as high quality.
        if confidence <= 0.0:
            confidence = 0.85

        if confidence < PARTNER_MIN_CONFIDENCE:
            continue

        partner_record["name"] = name

        partner_record["confidence"] = confidence

        real_partners.append(partner_record)

    return real_partners


# =========================================
# PRODUCTION PROVENANCE CHECKS
# =========================================

def is_mock_parsed_file(file_name):
    normalized = file_name.lower()

    return (
        normalized.startswith("https___mock_investor_")
        or "mock_investor" in normalized
    )


def has_raw_crawl_provenance(file_name, data):
    source_url = str(data.get("source_url", "")).strip()

    if not source_url or is_rejected_url(source_url):
        return False, "missing_or_rejected_source_url"

    if data.get("ingestion_source") and data.get("ingestion_source") != "web_crawl":
        return False, "non_web_crawl_source"

    if not INGESTION_REQUIRE_RAW_PROVENANCE:
        return True, "ok"

    markdown_file = data.get("raw_markdown_file") or file_name.replace(".json", ".md")
    metadata_file = data.get("raw_metadata_file") or file_name

    markdown_path = os.path.join(RAW_DATA_FOLDER, markdown_file)
    metadata_path = os.path.join(RAW_DATA_FOLDER, metadata_file)

    if not os.path.exists(markdown_path):
        return False, "missing_raw_markdown_file"

    if not os.path.exists(metadata_path):
        return False, "missing_raw_metadata_file"

    try:
        with open(metadata_path, "r", encoding="utf-8") as metadata_handle:
            metadata = json.load(metadata_handle)
    except Exception:
        return False, "invalid_raw_metadata_file"

    metadata_url = str(metadata.get("url", "")).strip()
    if metadata_url != source_url:
        return False, "source_url_metadata_mismatch"

    if metadata.get("ingestion_source") not in ("web_crawl", None):
        return False, "metadata_not_web_crawl"

    return True, "ok"


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

        is_valid, reason, data = validate_parsed_investor(data)

        if not is_valid:
            print(f"Skipping ({reason}): {data.get('firm_name', '')!r}")
            return False

        firm_name = normalize_firm_name(data.get("firm_name", ""))
        website = str(data.get("website", "")).strip()
        source_url = str(data.get("source_url", "")).strip()


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


        partners = filter_real_partners(

            data.get(

                "partners",

                []
            )
        )


        portfolio_companies = data.get("portfolio_companies", [])

        deduped_portfolio = {}
        for company in portfolio_companies:
            if isinstance(company, dict):
                company_name = str(company.get("company_name", "")).strip()
                sector = str(company.get("sector", "")).strip()
            else:
                company_name = str(company).strip()
                sector = ""
            if company_name:
                deduped_portfolio[company_name.lower()] = {
                    "company_name": company_name,
                    "sector": sector,
                }
        portfolio_companies = list(deduped_portfolio.values())


        # =====================================
        # EMBEDDING TEXT
        # =====================================

        pc_names = []
        for pc in portfolio_companies:
            if isinstance(pc, dict):
                pc_names.append(pc.get("company_name", ""))
            else:
                pc_names.append(str(pc))

        embedding_text = " ".join([

            firm_name,

            website,

            " ".join(focus_sectors),

            " ".join(investment_stage),

            " ".join(geography),

            " ".join(
                partner["name"]
                for partner in partners
            ),

            " ".join(pc_names)
        ])


        # =====================================
        # GENERATE EMBEDDING
        # =====================================

        model = get_embedding_model()

        embedding = model.encode(

            embedding_text
        ).tolist()


        # =====================================
        # DUPLICATE CHECK (name, normalized key, domain)
        # =====================================

        investor_id = find_duplicate_investor_id(
            cursor,
            firm_name,
            website=website,
            source_url=source_url,
        )

        if investor_id:


            cursor.execute(
                """
                UPDATE investors
                SET
                    firm_name = %s,
                    website = %s,
                    source_url = %s,
                    focus_sectors = %s,
                    investment_stage = %s,
                    geography = %s,
                    embedding = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                (
                    firm_name,
                    website or None,
                    source_url or None,
                    focus_sectors,
                    investment_stage,
                    geography,
                    embedding,
                    datetime.utcnow(),
                    investor_id,
                ),
            )

            print(f"Updated investor: {firm_name}")

        else:

            cursor.execute(

                """
                INSERT INTO investors (

                    firm_name,

                    website,

                    source_url,

                    focus_sectors,

                    investment_stage,

                    geography,

                    embedding,

                    created_at,

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

                    firm_name,

                    website,

                    source_url,

                    focus_sectors,

                    investment_stage,

                    geography,

                    embedding,

                    datetime.utcnow(),

                    datetime.utcnow()
                )
            )


            investor_id = cursor.fetchone()[0]


            print(

                f"Inserted investor: {firm_name}"
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

                    name,

                    role,

                    linkedin_url,

                    twitter_url

                )

                VALUES (

                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,

                (

                    investor_id,

                    partner.get("name", ""),

                    partner.get("role", ""),

                    partner.get("linkedin_url", ""),

                    partner.get("twitter_url", "")
                )
            )


        # =====================================
        # INSERT PORTFOLIO COMPANIES
        # =====================================

        for company in portfolio_companies:
            company_name = company.get("company_name", "")
            sector = company.get("sector", "")
            if not company_name:
                continue

            cursor.execute(
                """
                INSERT INTO portfolio_companies (
                    investor_id,
                    company_name,
                    sector
                )
                SELECT %s, %s, %s
                WHERE NOT EXISTS (
                    SELECT 1 FROM portfolio_companies
                    WHERE investor_id = %s
                      AND LOWER(company_name) = LOWER(%s)
                )
                """,
                (
                    investor_id,
                    company_name,
                    sector,
                    investor_id,
                    company_name,
                ),
            )


        if should_close_conn:

            conn.commit()


        return True


    except Exception as insertion_error:

        if should_close_conn:

            conn.rollback()

        import traceback
        traceback.print_exc()

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

    PARSED_FOLDER = PARSED_DATA_FOLDER


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

        if is_mock_parsed_file(file_name) and not INGESTION_ALLOW_MOCK_DATA:
            print(f"Skipping mock parsed file: {file_name}")
            continue

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

            has_provenance, provenance_reason = has_raw_crawl_provenance(
                file_name,
                data
            )

            if not has_provenance:
                print(
                    f"Skipping non-production parsed file "
                    f"({provenance_reason}): {file_name}"
                )
                continue


            insert_investor_data(data, conn=conn)


        except Exception as file_error:

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
