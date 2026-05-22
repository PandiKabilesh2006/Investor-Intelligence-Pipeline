from firecrawl import FirecrawlApp
from app.config.settings import FIRECRAWL_API_KEY

from app.utils.failed_url_manager import add_failed_url

firecrawl = FirecrawlApp(api_key=FIRECRAWL_API_KEY)

# =========================================
# WEBSITE EXTRACTION
# =========================================

def extract_website(url):

    try:

        # =====================================
        # FIRECRAWL EXTRACTION
        # =====================================

        response = firecrawl.scrape(

            url=url,

            formats=["markdown"]
        )


        # =====================================
        # VALIDATE RESPONSE
        # =====================================

        if not response:

            raise Exception(

                "Empty Firecrawl response"
            )


        # =====================================
        # EXTRACT MARKDOWN
        # =====================================

        markdown = response.get(

            "markdown",

            ""
        )


        if not markdown:

            raise Exception(

                "No markdown extracted"
            )


        # =====================================
        # SUCCESS
        # =====================================

        print(

            f"Extraction success: {url}"
        )


        return markdown


    # =========================================
    # EXTRACTION FAILURE
    # =========================================

    except Exception as extraction_error:

        print(

            f"Extraction failed: "
            f"{url} | "
            f"{extraction_error}"
        )


        # =====================================
        # STORE FAILED URL
        # =====================================

        add_failed_url(

            url,

            extraction_error
        )


        return None

    