import time
import schedule
import subprocess


# =========================================
# NIGHTLY INGESTION TASK
# =========================================

def run_nightly_pipeline():

    print("\n" + "=" * 80)

    print(

        "\nStarting scheduled investor ingestion...\n"
    )


    try:

        subprocess.run(

            [

                "py",

                "nightly_ingestion.py"
            ],

            check=True
        )


        print(

            "\nScheduled ingestion completed.\n"
        )


    except Exception as error:

        print(

            f"\nScheduler error: {error}\n"
        )


    print("=" * 80)


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

    schedule.run_pending()

    time.sleep(60)