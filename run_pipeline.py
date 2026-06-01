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

from urllib.parse import urlparse

warnings.filterwarnings("ignore")

from sqlalchemy import text

from app.database.db import SessionLocal

from app.search.tavily_search import (
    search_investors
)

from app.query.query_generator import (
    expand_search_query_variants,
    generate_queries
)

from app.extraction.async_extract import (
    extract_urls_async
)

from app.relevance.relevance_classifier import (
    classify_investor_relevance
)
from app.review_feedback import enqueue_review_item

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
from app.config.settings import (
    MAX_TOTAL_URLS,
    RECRAWL_AFTER_DAYS,
    TEST_MODE,
    TEST_QUERY_LIMIT,
    TEST_URL_LIMIT,
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
# URL CANONICALIZATION
# =========================================

def canonicalize_url(url):

    try:

        parsed = urlparse(url)

        scheme = "https"

        netloc = parsed.netloc.lower()

        if netloc.startswith("www."):

            netloc = netloc[4:]

        path = parsed.path.rstrip("/")

        canonical_url = (

            f"{scheme}://"
            f"{netloc}"
            f"{path}"
        )

        return canonical_url

    except Exception:

        return url


# =========================================
# DATABASE HELPERS
# =========================================

def already_crawled(url):

    session = SessionLocal()

    try:

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

        if not result:

            return False

        updated_at = result[0]

        if not updated_at:

            return False

        cutoff = (

            datetime.utcnow()

            -

            timedelta(
                days=RECRAWL_AFTER_DAYS
            )
        )

        if updated_at > cutoff:

            return True

        return False

    finally:

        session.close()


def load_rejected_or_blocked_hosts():

    session = SessionLocal()

    try:

        rows = session.execute(

            text(

                """
                SELECT url
                FROM failed_urls
                WHERE status = 'blocked'

                UNION

                SELECT url
                FROM review_queue
                WHERE status = 'rejected'
                  AND url IS NOT NULL
                """
            )
        ).fetchall()

        hosts = set()

        for row in rows:

            try:

                host = (
                    urlparse(row[0]).hostname
                    or
                    ""
                ).lower()

                if host.startswith("www."):

                    host = host[4:]

                if host:

                    hosts.add(host)

            except Exception:

                continue

        return hosts

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

    queries = expand_search_query_variants(sys.argv[1])

else:

    queries = generate_ingestion_queries()


# =========================================
# GLOBAL QUERY DEDUPLICATION
# =========================================

seen_queries = set()
deduped_queries = []

for query in queries:

    cleaned_query = str(query).strip()

    query_key = cleaned_query.lower()

    if cleaned_query and query_key not in seen_queries:

        seen_queries.add(query_key)

        deduped_queries.append(cleaned_query)

queries = deduped_queries


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
# BLOCKED DOMAINS
# =========================================

blocked_domains = [

    "bloomberg.com",

    "businessinsider.com",

    "cnbc.com",

    "economictimes.indiatimes.com",

    "linkedin.com",

    "youtube.com",

    "facebook.com",

    "instagram.com",

    "twitter.com",

    "reddit.com",

    "tiktok.com",

    "wikipedia.org"
]


NOISY_CONTENT_DOMAINS = {
    "bloomberg.com",
    "businessinsider.com",
    "cnbc.com",
    "economictimes.indiatimes.com",
    "forbes.com",
    "fortune.com",
    "medium.com",
    "moneycontrol.com",
    "nytimes.com",
    "reuters.com",
    "substack.com",
    "wsj.com",
}

INVESTOR_DIRECTORY_DOMAINS = {
    "openvc.app",
    "signal.nfx.com",
    "seedtable.com",
    "shizune.co",
}


NOISY_CONTENT_PATH_PARTS = {
    "blog",
    "blogs",
    "news",
    "article",
    "articles",
    "press",
    "press-release",
    "press-releases",
    "newsletter",
    "insights",
    "resources",
    "content",
    "events",
}


# =========================================
# SESSION URL DEDUPLICATION
# =========================================

seen_urls = set()
search_result_by_url = {}
urls_by_hostname = {}
dynamic_blocked_hosts = load_rejected_or_blocked_hosts()


HIGH_SIGNAL_URL_PARTS = {
    "about",
    "team",
    "people",
    "partners",
    "portfolio",
    "companies",
    "thesis",
    "focus",
    "investment",
    "investments",
    "contact",
}


def has_high_signal_path(url):

    try:

        path_parts = {
            part
            for part in re.split(
                r"[^a-z0-9]+",
                urlparse(url).path.lower()
            )
            if part
        }

        return bool(path_parts & HIGH_SIGNAL_URL_PARTS)

    except Exception:

        return False


def should_skip_collection_url(url):

    try:

        parsed = urlparse(url)

        hostname = (
            parsed.hostname
            or
            ""
        ).lower()

        path_parts = {
            part
            for part in re.split(
                r"[^a-z0-9-]+",
                parsed.path.lower()
            )
            if part
        }

    except Exception:

        return False

    if any(
        hostname == domain
        or
        hostname.endswith(f".{domain}")
        for domain in NOISY_CONTENT_DOMAINS
    ):

        return True

    if any(
        hostname == domain
        or
        hostname.endswith(f".{domain}")
        for domain in INVESTOR_DIRECTORY_DOMAINS
    ):

        return False

    if path_parts & NOISY_CONTENT_PATH_PARTS:

        return True

    return False


def hostname_for_url(url):
    try:
        return (urlparse(url).hostname or "").lower().replace("www.", "")
    except Exception:
        return ""


def is_blocked_site(url):
    host = hostname_for_url(url)

    if not host:
        return False

    return any(
        host == blocked_host
        or host.endswith(f".{blocked_host}")
        for blocked_host in dynamic_blocked_hosts
    )


def title_to_review_firm(title, url):
    title = (title or "").strip()
    words = re.findall(r"[A-Za-z0-9]+", title)

    if not title or len(words) > 10:
        return hostname_for_url(url)

    return title


def remember_search_result(url, title="", snippet="", query=""):
    hostname = hostname_for_url(url)

    if not hostname:
        return

    search_result_by_url[url] = {
        "title": title or "",
        "snippet": snippet or "",
        "query": query or "",
    }
    urls_by_hostname.setdefault(hostname, [])

    if url not in urls_by_hostname[hostname]:
        urls_by_hostname[hostname].append(url)


def ranked_alternate_urls(url):
    hostname = hostname_for_url(url)
    candidates = [
        candidate
        for candidate in urls_by_hostname.get(hostname, [])
        if candidate != url and not already_crawled(candidate)
        and not should_skip_collection_url(candidate)
        and not is_blocked_site(candidate)
        and not any(domain in candidate.lower() for domain in blocked_domains)
    ]

    return sorted(
        candidates,
        key=lambda candidate: (
            0 if has_high_signal_path(candidate) else 1,
            len(candidate),
        ),
    )[:3]


def enqueue_snippet_review(url, reason="Extraction failed"):
    metadata = search_result_by_url.get(url, {})
    title = metadata.get("title", "")
    snippet = metadata.get("snippet", "")

    if not title and not snippet:
        return

    enqueue_review_item(
        url=url,
        firm_name=title_to_review_firm(title, url),
        source_text=snippet,
        extracted_payload={
            "firm": "",
            "website": url,
            "source_url": url,
            "partners": [],
            "focus_sectors": [],
            "investment_stage": [],
            "portfolio_companies": [],
            "geography": [],
            "contact_links": [],
            "_fallback_source": "tavily_snippet",
            "_review_required": True,
            "search_title": title,
            "search_snippet": snippet,
        },
        ai_decision="snippet_fallback_needs_review",
        ai_confidence=0.20,
        ai_reason=(
            f"{reason}. Firecrawl could not extract enough page content, "
            "so only Tavily search title/snippet were queued. Edit before approval."
        ),
    )

    pipeline_logger.info(
        f"Queued Tavily snippet fallback for review: {url}"
    )


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
queued_this_run = 0
queued_urls_this_run = []
queue_mapping = {}


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

        max_pages = TEST_URL_LIMIT if TEST_MODE else 10

        search_results = search_investors(

            query=query,

            max_pages=max_pages
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

            remember_search_result(
                url,
                title=title,
                snippet=snippet,
                query=query,
            )

            url_lower = url.lower()

            blocked = False

            for domain in blocked_domains:

                if domain in url_lower:

                    blocked = True
                    break

            if blocked:

                continue

            if is_blocked_site(url):

                pipeline_logger.info(

                    f"Skipped human-rejected blocked site: {url}"
                )

                continue

            if should_skip_collection_url(url):

                pipeline_logger.info(

                    f"Skipped noisy collection URL: {url}"
                )

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

            if not is_relevant:

                continue

            if confidence < 0.65:
                enqueue_review_item(
                    url=url,
                    firm_name=title,
                    source_text=snippet,
                    extracted_payload={
                        "firm": title,
                        "website": url,
                        "source_url": url,
                        "partners": [],
                        "focus_sectors": [],
                        "investment_stage": [],
                        "portfolio_companies": [],
                        "geography": [],
                        "contact_links": [],
                    },
                    ai_decision=classification.get("relevance_tier", "low"),
                    ai_confidence=confidence,
                    ai_reason=classification.get("reason", ""),
                )

                pipeline_logger.info(
                    f"Sent low-confidence URL to review queue: {url}"
                )

                continue


            # =====================================
            # PRIORITY SCORING
            # =====================================

            priority_score = confidence


            if "portfolio" in url_lower:

                priority_score += 2


            if "team" in url_lower:

                priority_score += 2


            if "partner" in url_lower:

                priority_score += 2


            if "investor" in url_lower:

                priority_score += 1


            if has_high_signal_path(url):

                priority_score += 1


            # =====================================
            # ADD TO QUEUE
            # =====================================

            queue_id, inserted = add_to_crawl_queue(

                url,

                priority_score
            )

            if not inserted:

                continue

            queued_this_run += 1
            queued_urls_this_run.append(url)

            if queue_id:

                queue_mapping[url] = queue_id


            pipeline_logger.info(

                f"Queued URL: "
                f"{url} | "
                f"priority={priority_score}"
            )


    except Exception as search_error:

        error_logger.error(

            f"Search failed: "
            f"{search_error}"
        )


# =========================================
# PROCESS PRIORITY QUEUE
# =========================================

if queued_this_run == 0:

    pipeline_logger.warning(

        "No URLs queued from search results; skipping crawl processing"
    )

    print(

        "\nNo URLs queued from search results. "
        "Skipping crawl processing.\n"
    )

    raise SystemExit(0)

pipeline_logger.info(

    "Starting queued URL processing"
)


candidate_urls = queued_urls_this_run[:MAX_TOTAL_URLS]


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


fallback_results = []
fallback_attempted_urls = set()

for extraction_result in extraction_results:

    failed_url = extraction_result.get("url")
    markdown_content = extraction_result.get("markdown") or ""
    success = extraction_result.get("success")

    if success and len(markdown_content) >= 500:

        continue

    alternate_urls = [
        alternate_url
        for alternate_url in ranked_alternate_urls(failed_url)
        if alternate_url not in fallback_attempted_urls
    ]

    if alternate_urls:

        fallback_attempted_urls.update(alternate_urls)

        pipeline_logger.info(
            (
                f"Trying alternate public URLs for {failed_url}: "
                + ", ".join(alternate_urls)
            )
        )

        alternate_results = asyncio.run(
            extract_urls_async(
                alternate_urls
            )
        )

        usable_alternate = any(
            alternate_result.get("success")
            and len(alternate_result.get("markdown") or "") >= 500
            for alternate_result in alternate_results
        )

        fallback_results.extend(alternate_results)

        if not usable_alternate:

            enqueue_snippet_review(
                failed_url,
                reason="Primary and alternate public URLs failed extraction",
            )

        continue

    enqueue_snippet_review(
        failed_url,
        reason="Primary URL failed extraction",
    )

if fallback_results:

    extraction_results.extend(fallback_results)


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

        if len(markdown_content) < 500:

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
