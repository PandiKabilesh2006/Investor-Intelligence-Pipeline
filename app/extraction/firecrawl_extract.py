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

from app.utils.failed_url_manager import (
    add_failed_url
)


firecrawl = None


def get_firecrawl_client():
    global firecrawl

    if firecrawl is None:
        firecrawl = FirecrawlApp(
            api_key=FIRECRAWL_API_KEY
        )

    return firecrawl


def using_self_hosted_firecrawl():
    return bool(FIRECRAWL_API_URL)


def scrape_with_self_hosted_firecrawl(url):
    response = requests.post(
        f"{FIRECRAWL_API_URL}/v1/scrape",
        json={
            "url": url,
            "formats": [
                "markdown"
            ],
        },
        timeout=FIRECRAWL_TIMEOUT_SECONDS,
    )

    response.raise_for_status()
    payload = response.json()

    if not payload.get("success", False):
        raise Exception(
            payload.get("error") or "Self-hosted Firecrawl scrape failed"
        )

    data = payload.get("data") or {}
    return data.get("markdown", "")


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


    return list(

        set(urls)
    )


# =========================================
# SCRAPE SINGLE PAGE
# =========================================

def scrape_single_page(url):

    try:

        executor = ThreadPoolExecutor(max_workers=1)

        try:

            if using_self_hosted_firecrawl():

                future = executor.submit(

                    scrape_with_self_hosted_firecrawl,

                    url
                )

            else:

                future = executor.submit(

                    get_firecrawl_client().scrape,

                    url=url,

                    formats=["markdown"]
                )

            response = future.result(

                timeout=FIRECRAWL_TIMEOUT_SECONDS
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


        print(

            f"Extraction success: {url}"
        )


        return markdown


    except TimeoutError:

        extraction_error = (
            f"Timed out after {FIRECRAWL_TIMEOUT_SECONDS}s"
        )

        print(

            f"Extraction failed: "
            f"{url} | "
            f"{extraction_error}"
        )


        add_failed_url(

            url,

            extraction_error
        )


        return None


    except Exception as extraction_error:

        print(

            f"Extraction failed: "
            f"{url} | "
            f"{extraction_error}"
        )


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


        # =====================================
        # EXTRACT IMPORTANT PAGES
        # =====================================

        for subpage_url in subpage_urls:

            markdown = scrape_single_page(

                subpage_url
            )


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
