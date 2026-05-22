import time
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


# =========================================
# RETRY FAILED URLS
# =========================================

def retry_failed_urls():

    failed_urls = get_failed_urls()


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

                    "py",

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

        # =====================================
        # RUN MAIN PIPELINE
        # =====================================

        subprocess.run(

            [

                "py",

                "nightly_ingestion.py"
            ],

            check=True
        )


        pipeline_logger.info(

            "Scheduled ingestion completed"
        )


        # =====================================
        # RETRY FAILED URLS
        # =====================================

        retry_failed_urls()


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

schedule.every().day.at(

    "02:00"

).do(

    run_nightly_pipeline
)


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

    "Nightly ingestion scheduled at 02:00 AM"
)

pipeline_logger.info(

    "=" * 80
)


print("\n" + "=" * 80)

print(

    "\nInvestor Intelligence Scheduler Started\n"
)

print(

    "Nightly ingestion scheduled at 02:00 AM\n"
)

print("=" * 80)


# =========================================
# EVENT LOOP
# =========================================

while True:

    try:

        schedule.run_pending()

        time.sleep(60)


    except Exception as loop_error:

        error_logger.error(

            f"Scheduler loop error: "
            f"{loop_error}"
        )

        time.sleep(60)