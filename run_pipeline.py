import warnings
import time
import re
import os
import json

warnings.filterwarnings("ignore")

from app.search.tavily_search import search_investors
from app.extraction.firecrawl_extract import extract_website


# =========================================
# CONFIGURATION
# =========================================

MAX_RESULTS_PER_QUERY = 5

RAW_DATA_FOLDER = "raw_markdown"

os.makedirs(RAW_DATA_FOLDER, exist_ok=True)

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
# SINGLE INTELLIGENT QUERY
# =========================================

query=(
    f"top {sector} {stage} "
    f"venture capital firms "
    f"{theme} investors "
    f"in {geography}"
)

print("\nGenerated Query:\n")

print(query)


# =========================================
# FILTERING CONFIGURATION
# =========================================

blocked_domains = [
    "linkedin.com",
    "youtube.com",
    "twitter.com",
    "facebook.com",
    "instagram.com",
    "reddit.com",
    "tiktok.com"
]


# =========================================
# DOMAIN SIGNALS
# =========================================

preferred_domains = [
    ".vc",
    "ventures",
    "capital",
    "fund",
    "partners",
    "invest",
    "seed"
]


# =========================================
# POSITIVE SIGNALS
# =========================================

high_signal_paths = [
    "/team",
    "/portfolio",
    "/about",
    "/thesis",
    "/investments",
    "/people",
    "/partners",
    "/companies",
    "/focus",
    "/sectors"
]

high_signal_keywords = [
    "ventures",
    "capital",
    "fund",
    "vc",
    "invest",
    "partners"
]


# =========================================
# NEGATIVE SIGNALS
# =========================================

negative_keywords = [
    "blog",
    "news",
    "article",
    "latest",
    "realtime",
    "list",
    "2025",
    "2026",
    "media",
    "press",
    ".pdf",
    "rankings",
    "top-10",
    "top-20",
    "best"
]


# =========================================
# SEARCH PIPELINE
# =========================================

print("\nSearching investor websites...\n")

seen_urls = set()

try:

    search_results = search_investors(query)

    if "results" not in search_results:

        print("Search API error")
        print(search_results)

        exit()

    results = search_results["results"]

    if len(results) == 0:

        print("No search results found")
        exit()


    # =========================================
    # PROCESS TOP SEARCH RESULTS
    # =========================================

    for result in results[:MAX_RESULTS_PER_QUERY]:

        url = result.get("url", "")

        if not url:
            continue


        # =========================================
        # BLOCK BAD DOMAINS
        # =========================================

        blocked = False

        for domain in blocked_domains:

            if domain in url:

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

        url_lower = url.lower()

        score = 0


        # =========================================
        # DOMAIN SIGNALS
        # =========================================

        for keyword in preferred_domains:

            if keyword in url_lower:
                score += 4


        # =========================================
        # POSITIVE SIGNALS
        # =========================================

        for keyword in high_signal_keywords:

            if keyword in url_lower:
                score += 2


        for path in high_signal_paths:

            if path in url_lower:
                score += 3


        # =========================================
        # NEGATIVE SIGNALS
        # =========================================

        for keyword in negative_keywords:

            if keyword in url_lower:
                score -= 5


        # =========================================
        # PRECISION FILTERING
        # =========================================

        if score < 3:

            print(f"Skipping low-signal URL: {url}")
            continue


        print("=" * 80)

        print(f"\nProcessing URL: {url}")
        print(f"Signal Score: {score}\n")


        try:

            # =========================================
            # EXTRACTION
            # =========================================

            website_data = extract_website(url)

            markdown_content = website_data.markdown

            if not markdown_content:

                print("Empty markdown content")
                continue


            # =========================================
            # SAVE RAW MARKDOWN
            # =========================================

            safe_filename = re.sub(
                r'[^a-zA-Z0-9]',
                '_',
                url
            )

            filename = (
                f"{RAW_DATA_FOLDER}/"
                f"{safe_filename[:80]}.md"
            )

            with open(filename, "w", encoding="utf-8") as file:

                file.write(markdown_content)


            # =========================================
            # SAVE METADATA
            # =========================================

            metadata = {
                "query": query,
                "url": url,
                "score": score
            }

            metadata_filename = filename.replace(".md", ".json")

            with open(metadata_filename, "w", encoding="utf-8") as meta_file:

                json.dump(metadata, meta_file, indent=4)


            print(f"Saved markdown: {filename}")
            print(f"Saved metadata: {metadata_filename}\n")


            # =========================================
            # RATE LIMIT PROTECTION
            # =========================================

            time.sleep(2)

        except Exception as extraction_error:

            print(f"Extraction failed: {extraction_error}")

except Exception as search_error:

    print(f"Search failed: {search_error}")


print("\nPipeline execution completed.\n")
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