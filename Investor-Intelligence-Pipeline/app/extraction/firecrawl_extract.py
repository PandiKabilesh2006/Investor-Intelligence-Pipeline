import os
import hashlib
from firecrawl import FirecrawlApp
from app.config.settings import FIRECRAWL_API_KEY

_firecrawl = FirecrawlApp(api_key=FIRECRAWL_API_KEY)

# Define cache directory relative to the project root
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".cache", "firecrawl")

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)

class MockResponse:
    """A dummy object that mimics Firecrawl's ScrapeResponse so the pipeline doesn't break."""
    def __init__(self, markdown: str):
        self.markdown = markdown

def _get_cache_path(url: str) -> str:
    """Generate a safe, unique filename for a URL."""
    url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, f"{url_hash}.md")

def extract_website(url: str):
    """
    Extract markdown content from a URL using Firecrawl, with persistent local caching.
    Returns a ScrapeResponse (or MockResponse) object on success, or None on failure.
    """
    cache_path = _get_cache_path(url)

    # 1. Check cache
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                markdown = f.read()
            # We don't print here because run_pipeline.py handles the UI, 
            # but we can print a subtle tag so the user knows it was cached.
            print(" [CACHE HIT]", end="", flush=True)
            return MockResponse(markdown=markdown)
        except Exception:
            pass # If cache read fails, just fetch it normally

    # 2. Fetch from Firecrawl
    try:
        response = _firecrawl.scrape(
            url=url,
            formats=["markdown"],
        )
        
        # 3. Save to cache
        markdown = getattr(response, "markdown", "")
        if markdown:
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(markdown)
                
        return response

    except Exception as e:
        print(f"  ❌ Firecrawl extraction failed for {url}: {type(e).__name__}: {e}")
        return None