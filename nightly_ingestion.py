import subprocess
import time

from app.config.discovery_queries import (
    DISCOVERY_QUERIES
)


# =========================================
# NIGHTLY INVESTOR INGESTION
# =========================================

print(

    "\nStarting nightly investor ingestion...\n"
)


print(

    f"Generated "
    f"{len(DISCOVERY_QUERIES)} "
    f"discovery queries.\n"
)


# =========================================
# RUN DISCOVERY QUERIES
# =========================================

for index, query in enumerate(

    DISCOVERY_QUERIES,

    start=1
):

    print("=" * 80)

    print(

        f"\n[{index}/{len(DISCOVERY_QUERIES)}]"
    )

    print(

        f"Running query: {query}\n"
    )


    try:

        # =================================
        # RUN INGESTION PIPELINE
        # =================================

        subprocess.run(

            [

                "py",

                "run_pipeline.py",

                query
            ],

            check=True
        )


        # =============================
        # RATE LIMIT PROTECTION
        # =============================

        time.sleep(2)


    except Exception as error:

        print(

            f"\nQuery failed: {query}"
        )

        print(

            f"Error: {error}\n"
        )


# =========================================
# PARSE RAW MARKDOWN
# =========================================

print("=" * 80)

print(

    "\nParsing markdown files...\n"
)


subprocess.run(

    [

        "py",

        "parse_markdown.py"
    ]
)


# =========================================
# UPDATE DATABASE
# =========================================

print("=" * 80)

print(

    "\nUpdating PostgreSQL database...\n"
)


subprocess.run(

    [

        "py",

        "insert_into_db.py"
    ]
)


print("=" * 80)

print(

    "\nNightly investor ingestion completed.\n"
)