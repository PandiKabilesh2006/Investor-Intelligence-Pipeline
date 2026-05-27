from firecrawl import FirecrawlApp

from urllib.parse import urljoin

from app.config.settings import (
    EXTRACTION_SUBPAGES,
    FIRECRAWL_API_KEY,
    FIRECRAWL_API_URL
)

from app.utils.failed_url_manager import (
    add_failed_url
)


# =========================================
# FIRECRAWL CLIENT
# =========================================

firecrawl = FirecrawlApp(
    api_url=FIRECRAWL_API_URL,
    api_key=FIRECRAWL_API_KEY
)


# =========================================
# HIGH-SIGNAL SUBPAGES
# =========================================

DEFAULT_IMPORTANT_SUBPAGES = [

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


    for path in EXTRACTION_SUBPAGES or DEFAULT_IMPORTANT_SUBPAGES:

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

import requests
import re
from html.parser import HTMLParser

class HTMLToTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.ignore = False

    def handle_starttag(self, tag, attrs):
        if tag in ["script", "style", "nav", "footer", "header", "head"]:
            self.ignore = True

    def handle_endtag(self, tag):
        if tag in ["script", "style", "nav", "footer", "header", "head"]:
            self.ignore = False
        elif tag in ["p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "br"]:
            self.text.append("\n")

    def handle_data(self, data):
        if not self.ignore:
            cleaned = data.strip()
            if cleaned:
                self.text.append(cleaned + " ")

    def get_text(self):
        return re.sub(r'\n{3,}', '\n\n', "".join(self.text))

def scrape_fallback(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            parser = HTMLToTextParser()
            parser.feed(resp.text)
            text_content = parser.get_text()
            if len(text_content) >= 500:
                print(f"Fallback local scraper success: {url} ({len(text_content)} chars)")
                return text_content
        return None
    except Exception as fallback_err:
        print(f"Fallback local scraper failed: {url} | {fallback_err}")
        return None

def scrape_single_page(url):

    try:

        response = firecrawl.scrape(

            url=url,

            formats=["markdown"]
        )


        if not response:

            raise Exception("Empty response from Firecrawl")


        if isinstance(response, dict):

            markdown = response.get("markdown", "")

        else:

            markdown = getattr(response, "markdown", "") or ""


        if not markdown:

            raise Exception("No markdown content returned from Firecrawl")


        print(

            f"Extraction success: {url}"
        )


        return markdown


    except Exception as extraction_error:

        print(

            f"Firecrawl extraction failed: "
            f"{url} | "
            f"{extraction_error}"
        )

        print(f"Attempting local scraper fallback for: {url}")
        fallback_markdown = scrape_fallback(url)
        if fallback_markdown:
            return fallback_markdown

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
