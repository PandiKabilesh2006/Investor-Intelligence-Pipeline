from firecrawl import FirecrawlApp

from urllib.parse import urljoin

from app.config.settings import (
    FIRECRAWL_API_KEY
)

from app.utils.failed_url_manager import (
    add_failed_url
)


# =========================================
# FIRECRAWL CLIENT
# =========================================

firecrawl = FirecrawlApp(

    api_key=FIRECRAWL_API_KEY
)


# =========================================
# HIGH-SIGNAL SUBPAGES
# =========================================

IMPORTANT_SUBPAGES = [

    "",

    "/team",

    "/people",

    "/partners",

    "/about",

    "/leadership",

    "/portfolio",

    "/companies",

    "/contact"
]


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

        response = firecrawl.scrape(

            url=url,

            formats=["markdown"]
        )


        if not response:

            return None


        if isinstance(response, dict):

            markdown = response.get("markdown", "")

        else:

            markdown = getattr(response, "markdown", "") or ""


        if not markdown:

            return None


        print(

            f"Extraction success: {url}"
        )


        return markdown


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