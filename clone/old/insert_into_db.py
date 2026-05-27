import os
import json

from dotenv import load_dotenv

import psycopg2

from pgvector.psycopg2 import register_vector

from sentence_transformers import SentenceTransformer


# =========================================
# LOAD ENVIRONMENT VARIABLES
# =========================================

load_dotenv()


# =========================================
# DATABASE CONFIG
# =========================================

DB_HOST = os.getenv("DB_HOST", "localhost")

DB_NAME = os.getenv("DB_NAME", "postgres")

DB_USER = os.getenv("DB_USER", "postgres")

DB_PASSWORD = os.getenv("DB_PASSWORD", "2111")

DB_PORT = int(os.getenv("DB_PORT", "5432"))


# =========================================
# CONNECT TO POSTGRESQL
# =========================================

print("\nConnecting to PostgreSQL...\n")

conn = psycopg2.connect(

    host=DB_HOST,

    database=DB_NAME,

    user=DB_USER,

    password=DB_PASSWORD,

    port=DB_PORT
)

register_vector(conn)

cursor = conn.cursor()

print("Connected successfully.\n")


# =========================================
# ENABLE PGVECTOR EXTENSION
# =========================================

cursor.execute(

    """
    CREATE EXTENSION IF NOT EXISTS vector;
    """
)

conn.commit()


# =========================================
# CLEAN OLD BROKEN TABLES
# =========================================

print("Resetting database schema...\n")

cursor.execute(

    """
    DROP TABLE IF EXISTS portfolio_companies CASCADE;
    """
)

cursor.execute(

    """
    DROP TABLE IF EXISTS partners CASCADE;
    """
)

cursor.execute(

    """
    DROP TABLE IF EXISTS investors CASCADE;
    """
)

conn.commit()


# =========================================
# CREATE INVESTORS TABLE
# =========================================

cursor.execute(

    """
    CREATE TABLE investors (

        id SERIAL PRIMARY KEY,

        firm TEXT UNIQUE,

        website TEXT,

        focus_sectors TEXT[],

        investment_stage TEXT[],

        geography TEXT[],

        contact_links TEXT[],

        embedding vector(384),

        created_at TIMESTAMP DEFAULT NOW()
    );
    """
)


# =========================================
# CREATE PARTNERS TABLE
# =========================================

cursor.execute(

    """
    CREATE TABLE partners (

        id SERIAL PRIMARY KEY,

        investor_id INTEGER REFERENCES investors(id) ON DELETE CASCADE,

        name TEXT
    );
    """
)


# =========================================
# CREATE PORTFOLIO COMPANIES TABLE
# =========================================

cursor.execute(

    """
    CREATE TABLE portfolio_companies (

        id SERIAL PRIMARY KEY,

        investor_id INTEGER REFERENCES investors(id) ON DELETE CASCADE,

        company_name TEXT
    );
    """
)

conn.commit()

print("Database schema created successfully.\n")


# =========================================
# LOAD EMBEDDING MODEL
# =========================================

print("Loading embedding model...\n")

embedding_model = SentenceTransformer(

    "all-MiniLM-L6-v2"
)

print("Embedding model loaded.\n")


# =========================================
# PARSED JSON DIRECTORY
# =========================================

PARSED_FOLDER = "parsed_json"


if not os.path.exists(PARSED_FOLDER):

    raise FileNotFoundError(

        f"Folder not found: {PARSED_FOLDER}"
    )


# =========================================
# LOAD JSON FILES
# =========================================

json_files = [

    file

    for file in os.listdir(PARSED_FOLDER)

    if file.endswith(".json")
]


print(

    f"Found {len(json_files)} parsed JSON files.\n"
)


# =========================================
# PROCESS FILES
# =========================================

for file_name in json_files:

    print("=" * 80)

    print(

        f"\nProcessing file: "
        f"{file_name}\n"
    )

    file_path = os.path.join(

        PARSED_FOLDER,

        file_name
    )

    # =====================================
    # LOAD JSON
    # =====================================

    try:

        with open(

            file_path,

            "r",

            encoding="utf-8"
        ) as file:

            data = json.load(file)

    except Exception as load_error:

        print(

            f"Failed to load JSON: "
            f"{load_error}"
        )

        continue


    # =====================================
    # REQUIRED FIELD
    # =====================================

    firm = str(

        data.get(

            "firm",

            ""
        )

    ).strip()


    if not firm:

        print(

            f"Skipping file "
            f"(missing firm): "
            f"{file_name}"
        )

        continue


    # =====================================
    # OPTIONAL FIELDS
    # =====================================

    website = str(

        data.get(

            "website",

            ""
        )

    ).strip()


    focus_sectors = [

        str(item).strip()

        for item in data.get(

            "focus_sectors",

            []
        )

        if item
    ]


    investment_stage = [

        str(item).strip()

        for item in data.get(

            "investment_stage",

            []
        )

        if item
    ]


    geography = [

        str(item).strip()

        for item in data.get(

            "geography",

            []
        )

        if item
    ]


    contact_links = [

        str(item).strip()

        for item in data.get(

            "contact_links",

            []
        )

        if item
    ]


    partners = [

        str(item).strip()

        for item in data.get(

            "partners",

            []
        )

        if item
    ]


    portfolio_companies = [

        str(item).strip()

        for item in data.get(

            "portfolio_companies",

            []
        )

        if item
    ]


    # =====================================
    # BUILD EMBEDDING TEXT
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


    # =====================================
    # GENERATE EMBEDDING
    # =====================================

    try:

        embedding = embedding_model.encode(

            embedding_text
        ).tolist()

    except Exception as embedding_error:

        print(

            f"Embedding generation failed: "
            f"{embedding_error}"
        )

        continue


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
    # UPDATE EXISTING
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

            f"Updated investor: "
            f"{firm}"
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

            f"Inserted investor: "
            f"{firm}"
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


    # =====================================
    # SAVE CHANGES
    # =====================================

    conn.commit()

    print(

        f"Database commit completed "
        f"for {firm}\n"
    )


# =========================================
# CLOSE DATABASE CONNECTION
# =========================================

cursor.close()

conn.close()


print("=" * 80)

print("\nDatabase insertion complete.\n")