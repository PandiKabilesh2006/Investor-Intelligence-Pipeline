import warnings
import re
import os
import json
import asyncio
import sys

from datetime import (
    datetime,
    timedelta
)

warnings.filterwarnings("ignore")

from sqlalchemy import text

from app.database.db import SessionLocal

from app.config.settings import (
    INGESTION_MAX_URLS_PER_RUN,
    INGESTION_MIN_MARKDOWN_LENGTH,
    INGESTION_RECRAWL_AFTER_DAYS,
    INGESTION_SEARCH_MAX_PAGES,
    INGESTION_TEST_MODE,
    INGESTION_TEST_QUERY_LIMIT,
    RAW_DATA_FOLDER,
)
from app.validation.investor_validation import (
    canonicalize_url,
    is_investor_profile_url,
    is_rejected_url,
    should_queue_discovery_url,
)

from app.search.tavily_search import (
    search_investors
)

from app.query.query_generator import (
    generate_queries
)

from app.extraction.async_extract import (
    extract_urls_async
)

from app.relevance.relevance_classifier import (
    classify_investor_relevance
)

from app.config.ingestion_universe import (

    SECTORS,

    STAGES,

    GEOGRAPHIES,

    generate_ingestion_queries
)

from app.logging.logging_config import (

    pipeline_logger,

    error_logger
)

from app.utils.crawl_queue_manager import (

    add_to_crawl_queue,

    get_next_urls,

    mark_url_completed
)

from app.query.query_expansion import expand_query_theme


# =========================================
# INGESTION LIMITS
# =========================================

TEST_MODE = INGESTION_TEST_MODE

TEST_QUERY_LIMIT = INGESTION_TEST_QUERY_LIMIT

MAX_TOTAL_URLS = int(os.getenv(
    "INGESTION_RUN_URL_LIMIT",
    str(INGESTION_MAX_URLS_PER_RUN)
))

SEARCH_MAX_PAGES = INGESTION_SEARCH_MAX_PAGES

RECRAWL_AFTER_DAYS = INGESTION_RECRAWL_AFTER_DAYS


# =========================================
# RAW DATA FOLDER
# =========================================

os.makedirs(

    RAW_DATA_FOLDER,

    exist_ok=True
)


# =========================================
# DATABASE HELPERS
# =========================================

def already_crawled(url):

    session = SessionLocal()

    try:

        # Check if URL is already crawled and fresh
        result = session.execute(

            text(

                """
                SELECT updated_at

                FROM crawled_urls

                WHERE url = :url
                """
            ),

            {

                "url": url
            }
        ).fetchone()

        if result:

            updated_at = result[0]

            if updated_at:

                cutoff = (

                    datetime.utcnow()

                    -

                    timedelta(
                        days=RECRAWL_AFTER_DAYS
                    )
                )

                if updated_at > cutoff:

                    return True

        # Check if URL is already in crawl queue (pending or otherwise)
        queue_result = session.execute(

            text(

                """
                SELECT id

                FROM crawl_queue

                WHERE url = :url
                """
            ),

            {

                "url": url
            }
        ).fetchone()

        if queue_result:

            return True

        return False

    finally:

        session.close()


# =========================================
# SAVE CRAWL MEMORY
# =========================================

def save_crawled_url(

    url,

    query
):

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
# PIPELINE START
# =========================================

pipeline_logger.info(

    "Investor Intelligence Pipeline Started"
)


print(

    "\nInvestor Intelligence Pipeline\n"
)


# =========================================
# GLOBAL QUERY GENERATION
# =========================================

queries = []

if len(sys.argv) > 1:

    queries = [sys.argv[1]]

else:

    queries = generate_ingestion_queries()


# =========================================
# GLOBAL QUERY DEDUPLICATION
# =========================================

queries = list(set(queries))


# =========================================
# TEST MODE LIMITING
# =========================================

if TEST_MODE:

    queries = queries[:TEST_QUERY_LIMIT]


pipeline_logger.info(

    f"Generated {len(queries)} queries"
)


print(

    f"\nGenerated "
    f"{len(queries)} search queries\n"
)


# =========================================
# SESSION URL DEDUPLICATION
# =========================================

seen_urls = set()


# =========================================
# SEARCH PIPELINE
# =========================================

pipeline_logger.info(

    "Starting investor discovery"
)


print(

    "\nSearching investor websites...\n"
)

total_processed = 0


for query in queries:

    print("=" * 80)

    print(

        f"\nSearching Query: "
        f"{query}\n"
    )

    pipeline_logger.info(

        f"Searching query: {query}"
    )

    try:

        search_results = search_investors(

            query=query,

            max_pages=SEARCH_MAX_PAGES
        )

        if "results" not in search_results:

            error_logger.error(

                f"Search API error: "
                f"{search_results}"
            )

            continue

        results = search_results["results"]

        if len(results) == 0:

            pipeline_logger.warning(

                f"No results found for query: "
                f"{query}"
            )

            continue

        for result in results:

            url = result.get(

                "url",
                ""
            )

            url = canonicalize_url(url)

            title = result.get(

                "title",
                ""
            )

            snippet = result.get(

                "content",
                ""
            )

            if not url:

                continue

            if is_rejected_url(url):
                continue

            if already_crawled(url):

                continue

            if url in seen_urls:

                continue

            seen_urls.add(url)

            classification = (

                classify_investor_relevance(

                    query=query,

                    title=title,

                    url=url,

                    snippet=snippet
                )
            )

            is_relevant = classification.get(

                "is_relevant",

                False
            )

            confidence = classification.get(

                "confidence",

                0.0
            )

            should_queue, queue_reason = should_queue_discovery_url(url, classification)

            if not should_queue:
                pipeline_logger.info(f"Skipped URL ({queue_reason}): {url}")
                continue

            url_lower = url.lower()

            # =====================================
            # PRIORITY SCORING
            # =====================================

            priority_score = confidence

            if is_investor_profile_url(url):
                priority_score += 0.5

            # URL path signals — team/partner pages
            if "portfolio" in url_lower:

                priority_score += 2


            if "team" in url_lower:

                priority_score += 2


            if "partner" in url_lower:

                priority_score += 2


            if "people" in url_lower:

                priority_score += 2


            if "leadership" in url_lower:

                priority_score += 2


            if "about" in url_lower:

                priority_score += 1.5


            if "investor" in url_lower:

                priority_score += 1


            # .vc TLD = almost certainly a VC firm's own site
            if ".vc" in url_lower:
                priority_score += 1.5


            # source_type boost from classifier
            source_type = classification.get(
                "source_type",
                "investor_mention"
            )

            if source_type == "investor_profile":

                priority_score += 1.0


            # =====================================
            # ADD TO QUEUE
            # =====================================

            add_to_crawl_queue(

                url,

                priority_score
            )


            pipeline_logger.info(

                f"Queued URL: "
                f"{url} | "
                f"priority={priority_score:.2f} | "
                f"source_type={source_type}"
            )


    except Exception as search_error:

        error_logger.error(

            f"Search failed: "
            f"{search_error}"
        )


# =========================================
# PROCESS PRIORITY QUEUE
# =========================================

pipeline_logger.info(

    "Starting queued URL processing"
)


queued_urls = get_next_urls(

    limit=MAX_TOTAL_URLS
)


candidate_urls = []

queue_mapping = {}


for queued in queued_urls:

    queue_id = queued.id

    url = queued.url

    candidate_urls.append(url)

    queue_mapping[url] = queue_id


pipeline_logger.info(

    f"Processing {len(candidate_urls)} queued URLs"
)


print(

    f"\nRunning async extraction "
    f"for {len(candidate_urls)} URLs\n"
)


extraction_results = asyncio.run(

    extract_urls_async(

        candidate_urls
    )
)


# =========================================
# SAVE EXTRACTIONS
# =========================================

for extraction_result in extraction_results:

    try:

        url = extraction_result["url"]

        markdown_content = (

            extraction_result["markdown"]
        )

        success = extraction_result["success"]

        if not success:

            continue

        if not markdown_content:

            continue

        if len(markdown_content) < INGESTION_MIN_MARKDOWN_LENGTH:

            continue

        safe_filename = re.sub(

            r"[^a-zA-Z0-9]",

            "_",

            url
        )

        filename = (

            f"{RAW_DATA_FOLDER}/"
            f"{safe_filename[:120]}.md"
        )

        with open(

            filename,

            "w",

            encoding="utf-8"
        ) as file:

            file.write(

                markdown_content
            )

        metadata = {

            "url": url,

            "ingestion_source": "web_crawl",

            "content_type": "markdown",

            "markdown_length": len(markdown_content),

            "collected_at": str(
                datetime.utcnow()
            )
        }

        metadata_filename = (

            filename.replace(

                ".md",
                ".json"
            )
        )

        with open(

            metadata_filename,

            "w",

            encoding="utf-8"
        ) as meta_file:

            json.dump(

                metadata,

                meta_file,

                indent=4
            )

        save_crawled_url(

            url,

            "priority_queue"
        )

        queue_id = queue_mapping.get(url)

        if queue_id:

            mark_url_completed(

                queue_id
            )

        total_processed += 1

        pipeline_logger.info(

            f"Saved markdown: {filename}"
        )

        print(

            f"Saved markdown: "
            f"{filename}"
        )

    except Exception as save_error:

        error_logger.error(

            f"Save failed: "
            f"{save_error}"
        )

        print(

            f"Save failed: "
            f"{save_error}"
        )


# =========================================
# FINAL SUMMARY
# =========================================

pipeline_logger.info(

    f"Total processed: {total_processed}"
)

pipeline_logger.info(

    "Pipeline execution completed"
)


print("=" * 80)

print(

    f"\nTotal investor pages collected: "
    f"{total_processed}\n"
)

print(

    "Pipeline execution completed.\n"
)
# first_result = search_results["results"][0]

# url = first_result["url"]

# print(f"\nSearching URL: {url}\n")

# website_data = extract_website(url)

# markdown_content = website_data.markdown

# parsed_data = parse_investor(markdown_content)

# print(json.dumps(parsed_data, indent=4))
# # with open("output.md", "w", encoding="utf-8") as file:
# #     file.write(markdown_content)
# # print(markdown_content)
# print(search_results['results'][2])
