import warnings
import re
import os
import json
import logging
import asyncio

warnings.filterwarnings("ignore")

from app.search.tavily_search import search_investors

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

    GEOGRAPHIES
)


# =========================================
# TEST MODE
# =========================================

TEST_MODE = True

TEST_QUERY_LIMIT = 10

TEST_URL_LIMIT = 5


# =========================================
# LOGGING
# =========================================

logging.basicConfig(

    filename="pipeline.log",

    level=logging.INFO,

    format="%(asctime)s - %(levelname)s - %(message)s"
)


# =========================================
# RAW DATA FOLDER
# =========================================

RAW_DATA_FOLDER = "raw_markdown"

os.makedirs(

    RAW_DATA_FOLDER,

    exist_ok=True
)


# =========================================
# PIPELINE START
# =========================================

print(

    "\nInvestor Intelligence Pipeline\n"
)


# =========================================
# GLOBAL QUERY GENERATION
# =========================================

queries = []


for sector in SECTORS:

    for stage in STAGES:

        for geography in GEOGRAPHIES:

            generated_queries = (

                generate_queries(

                    sector=sector,

                    stage=stage,

                    geography=geography,

                    theme=sector
                )
            )


            queries.extend(

                generated_queries
            )


# =========================================
# GLOBAL QUERY DEDUPLICATION
# =========================================

queries = list(set(queries))


# =========================================
# TEST MODE LIMITING
# =========================================

if TEST_MODE:

    queries = queries[:TEST_QUERY_LIMIT]


print(

    f"\nGenerated "
    f"{len(queries)} search queries\n"
)


# =========================================
# BLOCKED DOMAINS
# =========================================

blocked_domains = [

    "linkedin.com",

    "youtube.com",

    "facebook.com",

    "instagram.com",

    "twitter.com",

    "reddit.com",

    "tiktok.com",

    "wikipedia.org"
]


# =========================================
# GLOBAL URL DEDUPLICATION
# =========================================

seen_urls = set()


# =========================================
# SEARCH PIPELINE
# =========================================

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

    logging.info(

        f"Searching query: {query}"
    )


    try:

        # =========================================
        # SEARCH INVESTORS
        # =========================================

        search_results = search_investors(

            query=query,

            max_pages=10
        )


        if "results" not in search_results:

            logging.error(

                f"Search API error: "
                f"{search_results}"
            )

            continue


        results = search_results["results"]


        if len(results) == 0:

            logging.warning(

                f"No results found for query: "
                f"{query}"
            )

            continue


        # =========================================
        # CANDIDATE URL QUEUE
        # =========================================

        candidate_urls = []


        # =========================================
        # SEMANTIC RELEVANCE FILTERING
        # =========================================

        for result in results:

            url = result.get(

                "url",
                ""
            )

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


            url_lower = url.lower()


            # =========================================
            # BLOCK BAD DOMAINS
            # =========================================

            blocked = False


            for domain in blocked_domains:

                if domain in url_lower:

                    blocked = True

                    break


            if blocked:

                print(

                    f"Skipping blocked domain: "
                    f"{url}"
                )

                continue


            # =========================================
            # GLOBAL URL DEDUPLICATION
            # =========================================

            if url in seen_urls:

                continue


            seen_urls.add(url)


            # =========================================
            # SEMANTIC RELEVANCE CLASSIFICATION
            # =========================================

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


            reason = classification.get(

                "reason",

                ""
            )


            # =========================================
            # CONFIDENCE FILTER
            # =========================================

            if not is_relevant:

                print(

                    f"Rejected URL: {url}"
                )

                continue


            if confidence < 0.75:

                print(

                    f"Low confidence URL: "
                    f"{url}"
                )

                continue


            print("=" * 80)

            print(

                f"\nQueued URL: {url}"
            )

            print(

                f"Relevance Confidence: "
                f"{confidence}"
            )

            print(

                f"Reason: "
                f"{reason}\n"
            )


            logging.info(

                f"Queued URL: "
                f"{url} | confidence={confidence}"
            )


            candidate_urls.append(url)


            # =========================================
            # TEST MODE URL LIMIT
            # =========================================

            if (

                TEST_MODE

                and

                len(candidate_urls)

                >= TEST_URL_LIMIT
            ):

                break


        # =========================================
        # RUN ASYNC EXTRACTION
        # =========================================

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
        # PROCESS EXTRACTION RESULTS
        # =========================================

        for extraction_result in extraction_results:

            url = extraction_result["url"]

            markdown_content = (

                extraction_result["markdown"]
            )

            success = extraction_result["success"]


            if not success:

                continue


            if not markdown_content:

                continue


            if len(markdown_content) < 500:

                print(

                    f"Insufficient content: "
                    f"{url}"
                )

                continue


            try:

                # =========================================
                # SAFE FILE NAME
                # =========================================

                safe_filename = re.sub(

                    r"[^a-zA-Z0-9]",

                    "_",

                    url
                )


                filename = (

                    f"{RAW_DATA_FOLDER}/"
                    f"{safe_filename[:120]}.md"
                )


                # =========================================
                # SAVE MARKDOWN
                # =========================================

                with open(

                    filename,

                    "w",

                    encoding="utf-8"
                ) as file:

                    file.write(

                        markdown_content
                    )


                # =========================================
                # SAVE METADATA
                # =========================================

                metadata = {

                    "query": query,

                    "url": url
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


                print(

                    f"Saved markdown: "
                    f"{filename}"
                )

                total_processed += 1


            except Exception as save_error:

                logging.error(

                    f"Save failed: "
                    f"{save_error}"
                )


                print(

                    f"Save failed: "
                    f"{save_error}"
                )


    except Exception as search_error:

        logging.error(

            f"Search failed: "
            f"{search_error}"
        )

        print(

            f"Search failed: "
            f"{search_error}"
        )


# =========================================
# FINAL SUMMARY
# =========================================

print("=" * 80)

print(

    f"\nTotal investor pages collected: "
    f"{total_processed}\n"
)

print(

    "Pipeline execution completed.\n"
)
# search_results = search_investors(query)
# # print(search_results)

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