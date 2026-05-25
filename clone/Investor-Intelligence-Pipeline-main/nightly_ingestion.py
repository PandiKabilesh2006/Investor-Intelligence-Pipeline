import subprocess
import time
import sys

from sqlalchemy import text

from app.config.discovery_queries import (
    DISCOVERY_QUERIES
)

from app.utils.crawl_queue_manager import (
    get_next_urls
)

from app.logging.logging_config import (

    pipeline_logger,

    error_logger
)

from app.database.db import SessionLocal

from app.extraction.firecrawl_extract import extract_website

from app.parsing.gpt_parser import parse_investor

from app.parsing.normalize import (
    normalize_investment_stages,
    normalize_sectors
)

from insert_into_db import insert_investor_data


# =========================================
# SAVE CRAWL MEMORY FOR INDIVIDUAL URL
# =========================================

def save_crawled_url(url, query):

    session = SessionLocal()

    try:

        session.execute(

            text(

                """
                INSERT INTO crawled_urls (

                    url,

                    discovered_query,

                    crawl_status,

                    markdown_saved,

                    updated_at

                )

                VALUES (

                    :url,

                    :query,

                    'success',

                    true,

                    NOW()
                )

                ON CONFLICT (url)

                DO UPDATE SET

                    updated_at = NOW(),

                    discovered_query = EXCLUDED.discovered_query
                """
            ),

            {

                "url": url,

                "query": query
            }
        )

        session.commit()

    finally:

        session.close()


# =========================================
# CHECK COMMAND LINE URL ARGUMENT
# =========================================

if len(sys.argv) > 1:

    url = sys.argv[1]

    # Check if the argument is a URL
    if url.startswith("http://") or url.startswith("https://"):

        pipeline_logger.info(f"Target URL reprocessing requested for: {url}")

        print(f"\nProcessing target URL: {url}\n")

        try:

            # Step 1: Scrape
            website_data = extract_website(url)

            if not website_data:

                raise Exception("No content returned from scrape")


            # Step 2: Parse
            parsed_data = parse_investor(website_data)


            # Step 3: Normalize
            parsed_data["focus_sectors"] = normalize_sectors(

                parsed_data.get("focus_sectors", [])
            )

            parsed_data["investment_stage"] = normalize_investment_stages(

                parsed_data.get("investment_stage", [])
            )

            parsed_data["source_url"] = url


            firm_name = parsed_data.get("firm", "")

            if isinstance(firm_name, list):

                firm_name = str(firm_name[0]) if len(firm_name) > 0 else ""

            firm_name = str(firm_name).strip()


            if not firm_name:

                raise Exception("Could not parse firm name from website content")


            parsed_data["firm"] = firm_name


            # Step 4: Insert/update database
            insert_investor_data(parsed_data)


            # Step 5: Save crawled URL status
            save_crawled_url(url, "reprocess_retry")


            pipeline_logger.info(f"Successfully reprocessed and inserted URL: {url}")

            print(f"\nSuccessfully reprocessed URL: {url}\n")


        except Exception as e:

            error_logger.error(f"Failed reprocessing URL {url}: {e}")

            print(f"\nError reprocessing URL {url}: {e}\n")

            from app.utils.failed_url_manager import add_failed_url

            add_failed_url(url, e)

            sys.exit(1)


        sys.exit(0)


# =========================================
# NIGHTLY INVESTOR INGESTION
# =========================================

pipeline_logger.info(

    "=" * 80
)

pipeline_logger.info(

    "Starting nightly investor ingestion"
)


print(

    "\nStarting nightly investor ingestion...\n"
)


# =========================================
# DISCOVERY QUERY METRICS
# =========================================

total_queries = len(

    DISCOVERY_QUERIES
)


pipeline_logger.info(

    f"Generated "
    f"{total_queries} "
    f"discovery queries"
)


print(

    f"Generated "
    f"{total_queries} "
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

        f"\n[{index}/{total_queries}]"
    )

    print(

        f"Running query: {query}\n"
    )


    pipeline_logger.info(

        f"Running query: {query}"
    )


    try:

        # =================================
        # RUN DISCOVERY PIPELINE
        # =================================

        subprocess.run(

            [

                sys.executable,

                "run_pipeline.py",

                query
            ],

            check=True
        )


        pipeline_logger.info(

            f"Query completed: {query}"
        )


        # =================================
        # RATE LIMIT PROTECTION
        # =================================

        time.sleep(2)


    except Exception as query_error:

        error_logger.error(

            f"Query failed | "
            f"Query: {query} | "
            f"Error: {query_error}"
        )


        print(

            f"\nQuery failed: {query}"
        )

        print(

            f"Error: {query_error}\n"
        )


# =========================================
# QUEUE STATUS
# =========================================

queued_urls = get_next_urls(

    limit=500
)


pipeline_logger.info(

    f"URLs currently queued: "
    f"{len(queued_urls)}"
)


print("=" * 80)

print(

    f"\nQueued URLs ready for extraction: "
    f"{len(queued_urls)}\n"
)


# =========================================
# PARSE RAW MARKDOWN
# =========================================

pipeline_logger.info(

    "Starting markdown parsing"
)


print("=" * 80)

print(

    "\nParsing markdown files...\n"
)


try:

    subprocess.run(

        [

            sys.executable,

            "parse_markdown.py"
        ],

        check=True
    )


    pipeline_logger.info(

        "Markdown parsing completed"
    )


except Exception as parse_error:

    error_logger.error(

        f"Markdown parsing failed: "
        f"{parse_error}"
    )


    print(

        f"\nMarkdown parsing failed: "
        f"{parse_error}\n"
    )


# =========================================
# UPDATE DATABASE
# =========================================

pipeline_logger.info(

    "Starting PostgreSQL update"
)


print("=" * 80)

print(

    "\nUpdating PostgreSQL database...\n"
)


try:

    subprocess.run(

        [

            sys.executable,

            "insert_into_db.py"
        ],

        check=True
    )


    pipeline_logger.info(

        "Database update completed"
    )


except Exception as database_error:

    error_logger.error(

        f"Database update failed: "
        f"{database_error}"
    )


    print(

        f"\nDatabase update failed: "
        f"{database_error}\n"
    )


# =========================================
# FINAL SUMMARY
# =========================================

pipeline_logger.info(

    "Nightly ingestion completed"
)

pipeline_logger.info(

    "=" * 80
)


print("=" * 80)

print(

    "\nNightly investor ingestion completed.\n"
)