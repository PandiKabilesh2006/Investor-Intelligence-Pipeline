import schedule
import time
import subprocess
import logging


# =========================================
# LOGGING
# =========================================

logging.basicConfig(

    filename="scheduler.log",

    level=logging.INFO,

    format="%(asctime)s - %(levelname)s - %(message)s"
)


# =========================================
# INGESTION WORKFLOW
# =========================================

def run_investor_pipeline():

    logging.info(

        "Starting investor ingestion pipeline"
    )


    try:

        # =========================================
        # STEP 1 — SEARCH + EXTRACTION
        # =========================================

        subprocess.run(

            ["python", "run_pipeline.py"],

            check=True
        )


        # =========================================
        # STEP 2 — PARSING
        # =========================================

        subprocess.run(

            ["python", "parse_markdown.py"],

            check=True
        )


        # =========================================
        # STEP 3 — DATABASE INSERTION
        # =========================================

        subprocess.run(

            ["python", "insert_into_db.py"],

            check=True
        )


        logging.info(

            "Investor ingestion completed successfully"
        )


    except Exception as error:

        logging.error(

            f"Pipeline failed: {error}"
        )


# =========================================
# NIGHTLY SCHEDULE
# =========================================

schedule.every().day.at(

    "02:00"
).do(

    run_investor_pipeline
)


# =========================================
# START SCHEDULER
# =========================================

print(

    "Investor ingestion scheduler started..."
)


logging.info(

    "Scheduler started"
)


# =========================================
# SCHEDULER LOOP
# =========================================

while True:

    schedule.run_pending()

    time.sleep(60)