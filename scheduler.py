import os
import time
import sys
from datetime import datetime, timezone

import schedule
import subprocess

from app.utils.failed_url_manager import (

    get_failed_urls,

    mark_failed_url_resolved
)

from app.logging.logging_config import (

    pipeline_logger,

    error_logger
)
from app.config.settings import (
    FAILED_URL_MAX_RETRIES,
    FAILED_URL_RETRY_LIMIT,
    RETRY_FAILED_URLS_ENABLED,
)


# =========================================
# RETRY FAILED URLS
# =========================================

def retry_failed_urls():

    failed_urls = get_failed_urls(
        max_retries=FAILED_URL_MAX_RETRIES,
        limit=FAILED_URL_RETRY_LIMIT,
    )


    pipeline_logger.info(

        f"Retrying "
        f"{len(failed_urls)} "
        f"failed URLs"
    )


    for failed in failed_urls:

        failed_id = failed["id"]

        url = failed["url"]


        try:

            pipeline_logger.info(

                f"Retrying failed URL: {url}"
            )


            # =================================
            # REPROCESS FAILED URL
            # =================================

            subprocess.run(

                [

                    sys.executable,

                    "nightly_ingestion.py",

                    url
                ],

                check=True
            )


            # =================================
            # MARK RESOLVED
            # =================================

            mark_failed_url_resolved(

                failed_id
            )


            pipeline_logger.info(

                f"Retry success: {url}"
            )


        except Exception as retry_error:

            error_logger.error(

                f"Retry failed | "
                f"URL: {url} | "
                f"Error: {retry_error}"
            )


# =========================================
# NIGHTLY INGESTION TASK
# =========================================

def run_nightly_pipeline():

    pipeline_logger.info(

        "=" * 80
    )

    pipeline_logger.info(

        "Starting scheduled investor ingestion"
    )


    try:
        run_started_timestamp = str(datetime.now(timezone.utc).timestamp())

        # =====================================
        # RUN DISCOVERY PIPELINE
        # =====================================

        pipeline_logger.info("Starting run_pipeline.py...")
        subprocess.run(

            [

                sys.executable,

                "run_pipeline.py"
            ],

            check=True
        )


        # =====================================
        # RUN MARKDOWN PARSING
        # =====================================

        pipeline_logger.info("Starting parse_markdown.py...")
        subprocess.run(

            [

                sys.executable,

                "parse_markdown.py"
            ],
            env={
                **os.environ,
                "PIPELINE_RUN_STARTED_TS": run_started_timestamp,
            },
            check=True
        )


        # =====================================
        # RUN DATABASE INSERTION
        # =====================================

        pipeline_logger.info("Starting insert_into_db.py...")
        subprocess.run(

            [

                sys.executable,

                "insert_into_db.py"
            ],
            env={
                **os.environ,
                "PIPELINE_RUN_STARTED_TS": run_started_timestamp,
            },
            check=True
        )


        pipeline_logger.info(

            "Scheduled ingestion completed"
        )


        # =====================================
        # RETRY FAILED URLS
        # =====================================

        if RETRY_FAILED_URLS_ENABLED:
            retry_failed_urls()
        else:
            pipeline_logger.info("Failed URL retry skipped by configuration")


        pipeline_logger.info(

            "Failed URL retry completed"
        )


    except Exception as scheduler_error:

        error_logger.error(

            f"Scheduler error: "
            f"{scheduler_error}"
        )


    pipeline_logger.info(

        "=" * 80
    )


# =========================================
# SCHEDULE CONFIGURATION
# =========================================
# 24-hour local time, e.g. "12:00" = noon. Override with SCHEDULE_TIME in .env
# Production default: 02:00. Keep this process running — closing the terminal stops scheduling.

SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "12:00")

schedule.every().day.at(SCHEDULE_TIME).do(run_nightly_pipeline)


# =========================================
# START SCHEDULER
# =========================================

pipeline_logger.info(

    "=" * 80
)

pipeline_logger.info(

    "Investor Intelligence Scheduler Started"
)

pipeline_logger.info(

    f"Nightly ingestion scheduled daily at {SCHEDULE_TIME} (local time)"
)

pipeline_logger.info(

    "=" * 80
)


print("\n" + "=" * 80)

print(

    "\nInvestor Intelligence Scheduler Started\n"
)

print(

    f"Nightly ingestion scheduled daily at {SCHEDULE_TIME} (local time)\n"
)

print(

    f"Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} — leave this window open.\n"
)

print("=" * 80)


# =========================================
# EVENT LOOP
# =========================================

while True:

    try:

        schedule.run_pending()

        time.sleep(30)


    except Exception as loop_error:

        error_logger.error(

            f"Scheduler loop error: "
            f"{loop_error}"
        )

        time.sleep(60)
