from firecrawl import FirecrawlApp
import requests

from urllib.parse import urljoin
from concurrent.futures import (
    ThreadPoolExecutor,
    TimeoutError
)

from app.config.settings import (
    FIRECRAWL_API_KEY,
    FIRECRAWL_API_URL,
    FIRECRAWL_TIMEOUT_SECONDS
)
from app.config.taxonomy import FIRECRAWL_IMPORTANT_SUBPAGES
from app.config.extraction_policy import BLOCKED_REVIEW_REASON

from app.utils.failed_url_manager import (
    add_failed_url,
    mark_url_blocked
)
from app.utils.blocked_url_detector import (
    BlockedUrlError,
    looks_blocked,
    raise_if_blocked,
)
from app.review_feedback import enqueue_review_item


firecrawl = None
blocked_urls_this_process = set()


def get_firecrawl_client():
    global firecrawl

    if firecrawl is None:
        firecrawl = FirecrawlApp(
            api_key=FIRECRAWL_API_KEY
        )

    return firecrawl


def using_self_hosted_firecrawl():
    return bool(FIRECRAWL_API_URL)


def scrape_with_self_hosted_firecrawl(url, timeout_seconds=None):
    timeout_seconds = timeout_seconds or FIRECRAWL_TIMEOUT_SECONDS

    response = requests.post(
        f"{FIRECRAWL_API_URL}/v1/scrape",
        json={
            "url": url,
            "formats": [
                "markdown"
            ],
        },
        timeout=timeout_seconds,
    )

    raise_if_blocked(
        url=url,
        status_code=response.status_code,
        text=response.text,
    )

    response.raise_for_status()
    payload = response.json()

    if not payload.get("success", False):
        error_message = payload.get("error") or "Self-hosted Firecrawl scrape failed"
        raise_if_blocked(
            url=url,
            text=str(payload),
            error_message=error_message,
        )
        raise Exception(
            error_message
        )

    data = payload.get("data") or {}
    return data.get("markdown", "")


def mark_extraction_blocked(url, error_message):
    blocked_urls_this_process.add(url)
    mark_url_blocked(
        url=url,
        error_message=error_message,
    )
    enqueue_review_item(
        url=url,
        firm_name="",
        source_text=str(error_message),
        extracted_payload={
            "url": url,
            "status": "blocked",
            "reason": BLOCKED_REVIEW_REASON,
        },
        ai_decision="blocked_extraction",
        ai_confidence=0.0,
        ai_reason=BLOCKED_REVIEW_REASON,
    )


# =========================================
# HIGH-SIGNAL SUBPAGES
# =========================================

IMPORTANT_SUBPAGES = FIRECRAWL_IMPORTANT_SUBPAGES


# =========================================
# GENERATE SUBPAGE URLS
# =========================================

def generate_subpage_urls(base_url):

    urls = []


    for path in IMPORTANT_SUBPAGES:

        full_url = urljoin(

            base_url,

            path
        )

        urls.append(

            full_url
        )


    deduped_urls = []
    seen_urls = set()

    for url in urls:

        if url in seen_urls:

            continue

        seen_urls.add(url)
        deduped_urls.append(url)

    return deduped_urls


# =========================================
# SCRAPE SINGLE PAGE
# =========================================

def scrape_single_page(
    url,
    timeout_seconds=None,
    record_failure=True,
):
    timeout_seconds = timeout_seconds or FIRECRAWL_TIMEOUT_SECONDS

    try:

        executor = ThreadPoolExecutor(max_workers=1)

        try:

            if using_self_hosted_firecrawl():

                future = executor.submit(

                    scrape_with_self_hosted_firecrawl,

                    url,

                    timeout_seconds
                )

            else:

                future = executor.submit(

                    get_firecrawl_client().scrape,

                    url=url,

                    formats=["markdown"]
                )

            response = future.result(

                timeout=timeout_seconds
            )

        finally:

            executor.shutdown(

                wait=False,

                cancel_futures=True
            )


        if not response:

            return None


        if isinstance(response, str):

            markdown = response

        elif isinstance(response, dict):

            markdown = response.get("markdown", "")

        else:

            markdown = getattr(response, "markdown", "") or ""


        if not markdown:

            return None

        raise_if_blocked(
            url=url,
            text=markdown[:4000],
        )


        print(

            f"Extraction success: {url}"
        )


        return markdown


    except TimeoutError:

        extraction_error = (
            f"Timed out after {timeout_seconds}s"
        )

        print(

            f"Extraction failed: "
            f"{url} | "
            f"{extraction_error}"
        )


        if record_failure:

            add_failed_url(

                url,

                extraction_error
            )


        return None


    except BlockedUrlError as extraction_error:

        print(

            f"Extraction blocked: "
            f"{url} | "
            f"{extraction_error}"
        )


        if record_failure:

            mark_extraction_blocked(

                url,

                extraction_error
            )


        return None


    except Exception as extraction_error:

        if looks_blocked(error_message=str(extraction_error)):

            print(

                f"Extraction blocked: "
                f"{url} | "
                f"{extraction_error}"
            )


            if record_failure:

                mark_extraction_blocked(

                    url,

                    extraction_error
                )


            return None

        print(

            f"Extraction failed: "
            f"{url} | "
            f"{extraction_error}"
        )


        if record_failure:

            add_failed_url(

                url,

                extraction_error
            )


        return None


# =========================================
# MULTI-PAGE WEBSITE EXTRACTION
# =========================================

def extract_website(url):

    try:

        # =====================================
        # GENERATE TARGET SUBPAGES
        # =====================================

        subpage_urls = generate_subpage_urls(

            url
        )


        combined_markdown = []
        blocked_subpages = []


        # =====================================
        # EXTRACT IMPORTANT PAGES
        # =====================================

        for subpage_url in subpage_urls:

            markdown = scrape_single_page(

                subpage_url
            )

            if subpage_url in blocked_urls_this_process:

                blocked_subpages.append(subpage_url)


            if markdown:

                combined_markdown.append(

                    f"\n\n"
                    f"====================\n"
                    f"URL: {subpage_url}\n"
                    f"====================\n\n"
                    f"{markdown}"
                )


        # =====================================
        # VALIDATE EXTRACTION
        # =====================================

        if not combined_markdown:

            if blocked_subpages:

                mark_extraction_blocked(

                    url,

                    (
                        "Blocked automated extraction for all usable pages: "
                        + ", ".join(blocked_subpages[:5])
                    )
                )

                return None

            raise Exception(

                "No markdown extracted "
                "from any subpage"
            )


        # =====================================
        # MERGE ALL CONTENT
        # =====================================

        final_markdown = (

            "\n\n".join(

                combined_markdown
            )
        )


        print(

            f"Combined extraction success: "
            f"{url}"
        )


        return final_markdown


    except Exception as extraction_error:

        if looks_blocked(error_message=str(extraction_error)):

            print(

                f"Website extraction blocked: "
                f"{url} | "
                f"{extraction_error}"
            )


            mark_extraction_blocked(

                url,

                extraction_error
            )


            return None

        print(

            f"Website extraction failed: "
            f"{url} | "
            f"{extraction_error}"
        )


        add_failed_url(

            url,

            extraction_error
        )


        return None


def extract_manual_review_url(url):
    markdown, _reason = extract_manual_review_url_with_reason(url)
    return markdown


def scrape_manual_review_page(url, timeout_seconds):
    try:
        executor = ThreadPoolExecutor(max_workers=1)

        try:
            if using_self_hosted_firecrawl():
                future = executor.submit(
                    scrape_with_self_hosted_firecrawl,
                    url,
                    timeout_seconds,
                )
            else:
                future = executor.submit(
                    get_firecrawl_client().scrape,
                    url=url,
                    formats=["markdown"],
                )

            response = future.result(timeout=timeout_seconds)

        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        if isinstance(response, str):
            markdown = response
        elif isinstance(response, dict):
            markdown = response.get("markdown", "")
        else:
            markdown = getattr(response, "markdown", "") or ""

        if not markdown:
            return None, "No markdown returned from extraction."

        raise_if_blocked(
            url=url,
            text=markdown[:4000],
        )

        print(f"Extraction success: {url}")
        return markdown, None

    except TimeoutError:
        reason = f"Timed out after {timeout_seconds}s"
        print(f"Extraction failed: {url} | {reason}")
        return None, reason

    except BlockedUrlError as extraction_error:
        reason = f"Blocked website: {extraction_error}"
        print(f"Extraction blocked: {url} | {extraction_error}")
        return None, reason

    except Exception as extraction_error:
        reason = str(extraction_error)

        if looks_blocked(error_message=reason):
            reason = f"Blocked website: {reason}"
            print(f"Extraction blocked: {url} | {reason}")
        else:
            print(f"Extraction failed: {url} | {reason}")

        return None, reason


def extract_manual_review_url_with_reason(url):
    manual_paths = [
        "",
        "/team/partners",
        "/team",
        "/people",
        "/our-team",
        "/portfolio",
        "/about",
    ]
    manual_timeout = min(15, FIRECRAWL_TIMEOUT_SECONDS)
    combined_markdown = []
    seen_urls = set()
    last_reason = "No markdown extracted from URL."

    for path in manual_paths:
        target_url = urljoin(url, path)

        if target_url in seen_urls:
            continue

        seen_urls.add(target_url)

        markdown, reason = scrape_manual_review_page(
            target_url,
            manual_timeout,
        )

        if markdown:
            combined_markdown.append(
                f"\n\n"
                f"====================\n"
                f"URL: {target_url}\n"
                f"====================\n\n"
                f"{markdown}"
            )

        if len(combined_markdown) >= 2:
            break

        if reason:
            last_reason = reason
            reason_text = reason.lower()

            if (
                "timed out" in reason_text
                or "blocked" in reason_text
                or "connection refused" in reason_text
                or "actively refused" in reason_text
                or "failed to establish a new connection" in reason_text
                or "max retries exceeded" in reason_text
            ):
                break

    if not combined_markdown:
        return None, last_reason

    return "\n\n".join(combined_markdown), None
