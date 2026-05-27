import time
import requests
from app.config.settings import TAVILY_API_KEY

_TAVILY_URL = "https://api.tavily.com/search"
_MAX_RETRIES = 2
_RETRY_DELAY = 2  # s   econds

# Domains to exclude from Tavily results — saves credits and avoids junk
_EXCLUDE_DOMAINS = [
    # Social / professional networks
    "linkedin.com", "twitter.com", "x.com", "facebook.com",
    "instagram.com", "youtube.com",
    # VC databases & aggregators
    "crunchbase.com", "pitchbook.com", "angellist.com", "wellfound.com",
    "tracxn.com", "dealroom.co", "openvc.app", "vcsheet.com",
    "shizune.co", "basetemplates.com", "f6s.com", "saasvclist.com",
    "vclist.co", "vcguide.co",
    # General media / news
    "medium.com", "forbes.com", "techcrunch.com", "hbr.org",
    "venturebeat.com", "wsj.com", "bloomberg.com", "reuters.com",
    "businessinsider.com", "wired.com", "theverge.com", "cnbc.com",
    "nytimes.com", "axios.com", "sifted.eu", "inc.com",
    "entrepreneur.com", "ft.com",
    # Generic blog / publishing platforms
    "wordpress.com", "substack.com", "ghost.io", "beehiiv.com",
]


def search_investors(query: str, max_results: int = 100, exclude_domains: list = None) -> dict:
    """
    Search Tavily for investor-related pages matching the query.
    Excludes known bad domains at the API level so we get real VC sites.
    Also dynamically excludes already scraped/processed domains to force Tavily to return brand-new leads.
    Retries up to _MAX_RETRIES times on failure.
    Returns a dict with a 'results' key (list) on success, or {'results': []} on failure.
    """
    combined_excludes = list(_EXCLUDE_DOMAINS)
    if exclude_domains:
        # Merge, ensuring no duplicates in the exclude list
        for d in exclude_domains:
            if d not in combined_excludes:
                combined_excludes.append(d)
                
    # Tavily API enforces a strict maximum of 150 exclude_domains.
    # If we have more than 150, we cap it here. Any domains beyond 150 that Tavily 
    # happens to return will still be safely filtered out locally by the pipeline's Smart Skip phase.
    if len(combined_excludes) > 150:
        combined_excludes = combined_excludes[:150]

    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced",
        "max_results": max_results,
        "include_answer": False,
        "include_raw_content": False,
        "exclude_domains": combined_excludes,
    }

    last_error = None
    for attempt in range(1, _MAX_RETRIES + 2):  # 1 initial + retries
        try:
            response = requests.post(
                _TAVILY_URL,
                json=payload,
                timeout=20,
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            last_error = f"Timeout on attempt {attempt}"
            print(f"  [!]  Tavily timeout (attempt {attempt}/{_MAX_RETRIES + 1})")

        except requests.exceptions.HTTPError as e:
            last_error = f"HTTP {e.response.status_code}"
            print(f"  [!]  Tavily HTTP error: {last_error} (attempt {attempt})")
            if e.response.text:
                print(f"  [!]  Tavily API Response: {e.response.text}")
            if e.response.status_code < 500:
                break

        except Exception as e:
            last_error = str(e)
            print(f"  [!]  Tavily error: {last_error} (attempt {attempt})")

        if attempt <= _MAX_RETRIES:
            time.sleep(_RETRY_DELAY)

    print(f"  [!]  Tavily search failed after {_MAX_RETRIES + 1} attempts: {last_error}")
    return {"results": []}