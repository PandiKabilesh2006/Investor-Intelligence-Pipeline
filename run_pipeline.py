import warnings
import time
import re
import os
import json
import logging
import asyncio

warnings.filterwarnings("ignore")

from app.search.tavily_search import search_investors
from app.query.query_generator import generate_queries
from app.extraction.async_extract import extract_urls_async


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

os.makedirs(RAW_DATA_FOLDER, exist_ok=True)


# =========================================
# CLEAN OLD RAW FILES
# =========================================

for file in os.listdir(RAW_DATA_FOLDER):

    file_path = f"{RAW_DATA_FOLDER}/{file}"

    if os.path.isfile(file_path):

        os.remove(file_path)


# =========================================
# USER INPUTS
# =========================================

print("\nInvestor Intelligence Pipeline\n")

sector = input("Enter startup sector: ")

stage = input("Enter investment stage: ")

geography = input("Enter geography: ")

theme = input("Enter investment theme: ")


# =========================================
# QUERY GENERATION
# =========================================

queries = generate_queries(

    sector,
    stage,
    geography,
    theme
)

print(f"\nGenerated {len(queries)} search queries\n")


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
    "crunchbase.com",
    "wikipedia.org"
]


# =========================================
# HIGH QUALITY VC DOMAIN SIGNALS
# =========================================

preferred_domain_keywords = [

    ".vc",
    "ventures",
    "capital",
    "fund",
    "partners",
    "invest",
    "seed",
    "equity",
    "portfolio",
    "management",
    "holdings",
    "accelerator",
    "thesis"
]


# =========================================
# HIGH SIGNAL URL PATHS
# =========================================

high_signal_paths = [

    "/team",
    "/people",
    "/partners",
    "/portfolio",
    "/companies",
    "/investments",
    "/thesis",
    "/focus",
    "/about",
    "/strategy",
    "/platform",
    "/who-we-are",
    "/what-we-do"
]


# =========================================
# STRONG VC KEYWORDS
# =========================================

high_signal_keywords = [

    "venture",
    "capital",
    "vc",
    "fund",
    "investor",
    "investment",
    "portfolio",
    "seed",
    "series-a",
    "series-b",
    "growth-equity",
    "private-equity",
    "startup",
    "founders",
    "backing",
    "thesis",
    "innovation"
]


# =========================================
# NEGATIVE SIGNALS
# =========================================

negative_keywords = [

    "blog",
    "news",
    "article",
    "latest",
    "press",
    "media",
    "realtime",
    "top-10",
    "top-20",
    "top-50",
    "rankings",
    "best",
    "jobs",
    "careers",
    "events",
    ".pdf",
    "podcast",
    "webinar",
    "newsletter"
]


# =========================================
# GLOBAL URL DEDUPLICATION
# =========================================

seen_urls = set()


# =========================================
# SEARCH PIPELINE
# =========================================

print("\nSearching investor websites...\n")

total_processed = 0


for query in queries:

    print("=" * 80)

    print(f"\nSearching Query: {query}\n")

    logging.info(f"Searching query: {query}")


    try:

        # =========================================
        # DYNAMIC PAGINATED SEARCH
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
        # PROCESS RESULTS
        # =========================================

        candidate_urls = []


        for result in results:

            url = result.get("url", "")

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

                print(f"Skipping blocked domain: {url}")

                continue


            # =========================================
            # URL DEDUPLICATION
            # =========================================

            if url in seen_urls:

                continue


            seen_urls.add(url)


            # =========================================
            # SIGNAL SCORING
            # =========================================

            score = 0


            # =========================================
            # DOMAIN SIGNALS
            # =========================================

            for keyword in preferred_domain_keywords:

                if keyword in url_lower:

                    score += 5


            # =========================================
            # HIGH SIGNAL KEYWORDS
            # =========================================

            for keyword in high_signal_keywords:

                if keyword in url_lower:

                    score += 3


            # =========================================
            # HIGH SIGNAL PATHS
            # =========================================

            for path in high_signal_paths:

                if path in url_lower:

                    score += 4


            # =========================================
            # NEGATIVE SIGNALS
            # =========================================

            for keyword in negative_keywords:

                if keyword in url_lower:

                    score -= 8


            # =========================================
            # QUERY TERM MATCHING
            # =========================================

            query_terms = query.lower().split()

            for term in query_terms:

                if term in url_lower:

                    score += 2


            # =========================================
            # PRECISION FILTERING
            # =========================================

            if score < 5:

                print(f"Skipping low-signal URL: {url}")

                continue


            print("=" * 80)

            print(f"\nQueued URL: {url}")

            print(f"Signal Score: {score}\n")


            logging.info(

                f"Queued URL: "
                f"{url} | score={score}"
            )


            candidate_urls.append(url)


        # =========================================
        # RUN ASYNC EXTRACTION
        # =========================================

        print(

            f"\nRunning async extraction "
            f"for {len(candidate_urls)} URLs\n"
        )


        extraction_results = asyncio.run(

            extract_urls_async(candidate_urls)
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
                # SAVE MARKDOWN
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


                with open(

                    filename,

                    "w",

                    encoding="utf-8"
                ) as file:

                    file.write(markdown_content)


                # =========================================
                # SAVE METADATA
                # =========================================

                metadata = {

                    "query": query,

                    "url": url
                }


                metadata_filename = (

                    filename.replace(".md", ".json")
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


                print(f"Saved markdown: {filename}")

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

            f"Search failed: {search_error}"
        )

        print(f"Search failed: {search_error}")


# =========================================
# FINAL SUMMARY
# =========================================

print("=" * 80)

print(

    f"\nTotal investor pages collected: "
    f"{total_processed}\n"
)

print("Pipeline execution completed.\n")
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