from firecrawl import FirecrawlApp
from app.config.settings import FIRECRAWL_API_KEY

firecrawl = FirecrawlApp(api_key=FIRECRAWL_API_KEY)

def extract_website(url):

    response = firecrawl.scrape(
        url=url,
        formats=["markdown"]
    )

    # return response
    return response