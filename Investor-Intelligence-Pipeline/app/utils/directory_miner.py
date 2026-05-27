"""
Directory miner: when we encounter a VC directory/aggregator page,
extract the actual VC firm URLs it links to instead of just skipping it.
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from typing import List


# Hints that suggest a URL is a VC firm's own site (not another directory)
_VC_HINTS = {"vc", "ventures", "capital", "fund", "partners", "invest", "seed"}

# Domains to exclude from mined results (directories, social, media)
_MINED_SKIP_DOMAINS = {
    "linkedin.com", "twitter.com", "x.com", "facebook.com", "instagram.com",
    "youtube.com", "crunchbase.com", "pitchbook.com", "angellist.com",
    "wellfound.com", "tracxn.com", "medium.com", "forbes.com",
    "techcrunch.com", "hbr.org", "venturebeat.com", "bloomberg.com",
    "google.com", "apple.com", "wikipedia.org", "github.com",
    # Known directories — don't mine these from other directories
    "openvc.app", "vcsheet.com", "shizune.co", "basetemplates.com",
    "dealroom.co", "f6s.com", "saasvclist.com",
}


def _is_skippable(url: str) -> bool:
    try:
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return any(s in domain for s in _MINED_SKIP_DOMAINS)
    except Exception:
        return True


def _score_url(url: str) -> int:
    """Higher score = more likely to be a real VC firm website."""
    lower = url.lower()
    return sum(hint in lower for hint in _VC_HINTS)


def mine_directory_links(url: str, max_links: int = 25) -> List[str]:
    """
    Scrape a directory/aggregator page and extract likely VC firm homepage URLs.
    Returns up to max_links deduplicated URLs, sorted by VC-hint score.
    """
    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            },
            timeout=12,
            allow_redirects=True,
        )
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        base_domain = urlparse(url).netloc.lower()

        seen: set[str] = set()
        candidates: list[str] = []

        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip()
            if not href:
                continue

            # Resolve relative URLs
            if href.startswith("/"):
                href = urljoin(url, href)

            if not href.startswith("http"):
                continue

            # Skip anchors, mailto, etc.
            parsed = urlparse(href)
            if not parsed.netloc:
                continue

            link_domain = parsed.netloc.lower()
            if link_domain.startswith("www."):
                link_domain = link_domain[4:]

            # Skip same domain (internal links of the directory site)
            if link_domain in base_domain or base_domain in link_domain:
                continue

            # Skip known junk domains
            if _is_skippable(href):
                continue

            # Normalize to homepage only
            homepage = f"{parsed.scheme}://{parsed.netloc}"
            key = homepage.lower().rstrip("/")

            if key not in seen:
                seen.add(key)
                candidates.append(homepage)

        # Sort by VC hint score (higher = more likely a real VC)
        candidates.sort(key=_score_url, reverse=True)
        return candidates[:max_links]

    except Exception as e:
        print(f"  [!]  Directory mining failed for {url}: {e}")
        return []
