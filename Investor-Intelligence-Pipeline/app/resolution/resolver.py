import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse


BLOCKED_DOMAINS = {
    "linkedin.com", "twitter.com", "x.com", "facebook.com",
    "instagram.com", "youtube.com", "crunchbase.com", "superscout.co",
    "tracxn.com", "pitchbook.com", "signal.nfx.com",
    "wellfound.com", "angellist.com",
}

GOOD_HINTS = ["vc", "ventures", "capital", "fund", "partners", "invest"]

# Cache: raw URL → resolved homepage URL
_resolve_cache: dict = {}


def _is_blocked_domain(url: str) -> bool:
    lower = url.lower()
    return any(blocked in lower for blocked in BLOCKED_DOMAINS)


def _normalize_to_homepage(url: str) -> str:
    """Strip path/query/fragment and return scheme://netloc"""
    parsed = urlparse(url)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()
    return f"{scheme}://{netloc}"


def _extract_external_links(url: str) -> list:
    """Scrape external links from a page (used only for blocked-domain fallback)."""
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=12,
            allow_redirects=True,
        )
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        links = []
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            if href.startswith("http"):
                links.append(href)
        return list(set(links))

    except Exception:
        return []


def resolve_official_website(url: str) -> str | None:
    """
    Return the homepage URL of the official VC website.

    - If the URL is not from a blocked domain, return its homepage directly.
    - If it is blocked, scrape the page for external links and pick the
      most likely VC domain.
    - Returns None if no good domain can be found.
    """
    # Cache check
    cache_key = url.lower().rstrip("/")
    if cache_key in _resolve_cache:
        return _resolve_cache[cache_key]

    if not _is_blocked_domain(url):
        homepage = _normalize_to_homepage(url)
        _resolve_cache[cache_key] = homepage
        return homepage

    # Blocked domain — try to extract the real website from linked pages
    links = _extract_external_links(url)
    if not links:
        _resolve_cache[cache_key] = None
        return None

    candidates = []
    for link in links:
        if _is_blocked_domain(link):
            continue
        homepage = _normalize_to_homepage(link)
        candidates.append(homepage)

    candidates = list(set(candidates))
    if not candidates:
        _resolve_cache[cache_key] = None
        return None

    # Prefer domains that contain VC-related hints
    ranked = sorted(
        candidates,
        key=lambda x: sum(hint in x.lower() for hint in GOOD_HINTS),
        reverse=True,
    )

    resolved = ranked[0]
    _resolve_cache[cache_key] = resolved
    return resolved