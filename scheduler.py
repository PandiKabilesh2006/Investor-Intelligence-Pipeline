import os
import sys
import subprocess
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

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
        f"Retrying {len(failed_urls)} failed URLs"
    )

    for failed in failed_urls:
        failed_id = failed["id"]
        url = failed["url"]

        try:
            pipeline_logger.info(
                f"Retrying failed URL: {url}"
            )

            # Reprocess failed URL via nightly_ingestion.py argument with unbuffered output
            with open("pipeline.log", "a", encoding="utf-8") as log_file:
                subprocess.run(
                    [
                        sys.executable,
                        "-u",
                        "nightly_ingestion.py",
                        url
                    ],
                    stdout=log_file,
                    stderr=log_file,
                    check=True
                )

            # Mark resolved
            mark_failed_url_resolved(failed_id)

            pipeline_logger.info(
                f"Retry success: {url}"
            )

        except Exception as retry_error:
            error_logger.error(
                f"Retry failed | URL: {url} | Error: {retry_error}"
            )


# =========================================
# NIGHTLY INGESTION TASK
# =========================================

def run_nightly_pipeline():
    pipeline_logger.info("=" * 80)
    pipeline_logger.info("Starting scheduled investor ingestion")

    try:
        # Run main ingestion script with unbuffered output redirected to pipeline.log
        with open("pipeline.log", "a", encoding="utf-8") as log_file:
            subprocess.run(
                [
                    sys.executable,
                    "-u",
                    "nightly_ingestion.py"
                ],
                stdout=log_file,
                stderr=log_file,
                check=True
            )

        pipeline_logger.info("Scheduled ingestion completed")

        # Retry failed URLs
        retry_failed_urls()

        pipeline_logger.info("Failed URL retry completed")

    except Exception as scheduler_error:
        error_logger.error(
            f"Scheduler error during pipeline execution: {scheduler_error}"
        )

    pipeline_logger.info("=" * 80)


# =========================================
# START SCHEDULER
# =========================================

if __name__ == "__main__":
    scheduler = BlockingScheduler()

    # Read cron schedule from environment, default to 2:00 PM daily ("0 14 * * *")
    cron_expr = os.getenv("INGESTION_CRON", "0 14 * * *")

    pipeline_logger.info(f"Initializing APScheduler with cron expression: '{cron_expr}'")

    fields = cron_expr.strip().split()
    if len(fields) == 5:
        trigger = CronTrigger(
            minute=fields[0],
            hour=fields[1],
            day=fields[2],
            month=fields[3],
            day_of_week=fields[4]
        )
    else:
        # Fallback to daily 2 PM if invalid
        trigger = CronTrigger(hour=14, minute=0)
        pipeline_logger.warning(
            f"Invalid cron expression '{cron_expr}' (must have exactly 5 fields). "
            f"Falling back to daily at 02:00 PM."
        )

    scheduler.add_job(
        run_nightly_pipeline,
        trigger=trigger,
        id="nightly_ingestion_job",
        name="Nightly Investor Intelligence Ingestion and Failed Url Retry"
    )

    print("\n" + "=" * 80)
    print(f"\nInvestor Intelligence Scheduler Started")
    print(f"Scheduled Job: Nightly ingestion scheduled via CRON: '{cron_expr}'\n")
    print("=" * 80)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pipeline_logger.info("Scheduler stopped.")
        print("\nScheduler stopped.")
