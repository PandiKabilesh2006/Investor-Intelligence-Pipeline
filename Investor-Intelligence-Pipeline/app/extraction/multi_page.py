"""
Multi-page scraper: after identifying a VC firm's homepage, discover and
scrape high-value sub-pages (team, portfolio, about) to enrich the content
before LLM parsing.

Credit cost: up to MAX_SUB_PAGES additional Firecrawl credits per firm.
"""

import re
from urllib.parse import urlparse, urljoin
from typing import Optional

from app.extraction.firecrawl_extract import extract_website


# ---------------------------------------------------------------------------
# Sub-page priority list (order matters — higher index = lower priority)
# ---------------------------------------------------------------------------

_PRIORITY_PATHS = [
    # Team / Partners — most valuable (gives us partner names + roles)
    "team", "people", "partners", "our-team", "meet-the-team",
    "leadership", "managing-partners", "general-partners",
    # Portfolio — second most valuable (investment history, companies)
    "portfolio", "investments", "companies", "portfolio-companies",
    "our-portfolio", "our-investments",
    # About / Thesis — investment criteria, fund info
    "about", "about-us", "firm", "who-we-are", "approach",
    "investment-thesis", "strategy", "focus", "what-we-do",
]

# Markdown link pattern: [text](url)
_LINK_RE = re.compile(r'\[([^\]]*)\]\(([^)\s]+)\)')

# File extensions to ignore
_IGNORE_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico",
    ".mp4", ".webm", ".avi", ".mov",
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
    ".zip", ".tar", ".gz", ".rar",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_domain(url: str) -> str:
    try:
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def _path_score(path: str) -> int:
    """Return a priority score for a URL path. Higher = more valuable."""
    path_lower = path.lower().strip("/")
    for rank, keyword in enumerate(_PRIORITY_PATHS):
        if keyword in path_lower:
            return len(_PRIORITY_PATHS) - rank  # inverted so higher index = higher score
    return 0


def _absolute(href: str, base_url: str) -> Optional[str]:
    """Resolve a possibly-relative href to an absolute URL."""
    href = href.strip()
    if not href or href.startswith("#") or href.startswith("mailto:"):
        return None
    if href.startswith("//"):
        scheme = urlparse(base_url).scheme or "https"
        return f"{scheme}:{href}"
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}{href}"
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def discover_sub_pages(
    homepage_url: str,
    homepage_markdown: str,
    max_pages: int = 2,
) -> list[str]:
    """
    Parse internal links from the homepage markdown and return the most
    promising sub-page URLs (team, portfolio, about, etc.).

    Only same-domain links are returned. No HTTP requests are made here.

    Args:
        homepage_url:      The firm's homepage URL
        homepage_markdown: Already-scraped homepage markdown (from Firecrawl)
        max_pages:         Max sub-pages to return

    Returns:
        List of absolute URLs sorted by priority score, length max_pages
    """
    if not homepage_markdown or max_pages <= 0:
        return []

    try:
        parsed = urlparse(homepage_url)
        home_domain = parsed.netloc.lower().lstrip("www.")
        base_url = f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        return []

    seen_paths: set[str] = set()
    candidates: list[tuple[str, int]] = []

    for _, href in _LINK_RE.findall(homepage_markdown):
        full_url = _absolute(href, base_url)
        if not full_url:
            continue

        # Only same-domain sub-pages
        link_domain = urlparse(full_url).netloc.lower()
        if link_domain.startswith("www."):
            link_domain = link_domain[4:]
        if link_domain != home_domain:
            continue

        path = urlparse(full_url).path.rstrip("/")
        if not path or path == "/":
            continue

        # Skip media/document files
        if any(path.lower().endswith(ext) for ext in _IGNORE_EXTS):
            continue

        score = _path_score(path)
        if score <= 0:
            continue

        # Normalise: drop query string and fragment for dedup
        clean_url = f"{base_url}{path}"
        if path in seen_paths:
            continue
        seen_paths.add(path)

        candidates.append((clean_url, score))

    candidates.sort(key=lambda x: x[1], reverse=True)
    return [url for url, _ in candidates[:max_pages]]


def scrape_and_merge(
    homepage_url: str,
    homepage_markdown: str,
    max_sub_pages: int = 2,
    verbose: bool = True,
) -> tuple[str, int]:
    """
    Scrape relevant sub-pages and merge with the homepage markdown.

    Returns:
        (merged_markdown, total_pages_scraped)
        merged_markdown has section headers so the LLM knows which page
        each chunk came from.
    """
    sections: list[str] = [
        f"=== HOMEPAGE ===\n{homepage_markdown}"
    ]
    extra_pages = 0

    # Feature B: Dynamic Crawl Termination
    # If the homepage is extremely rich and already contains team & portfolio indicators,
    # we bypass deep crawling to save Firecrawl credits.
    text_lower = homepage_markdown.lower()
    has_team = any(t in text_lower for t in ["team", "people", "partners", "founders", "leadership"])
    has_portfolio = any(t in text_lower for t in ["portfolio", "investments", "companies", "thesis", "stage"])
    
    if len(homepage_markdown) > 8000 and has_team and has_portfolio:
        if verbose:
            print(" [SKIP SUB-PAGES - Homepage contains deep info]", end="", flush=True)
        return homepage_markdown, 1

    sub_urls = discover_sub_pages(homepage_url, homepage_markdown, max_pages=max_sub_pages)

    for sub_url in sub_urls:
        path_label = urlparse(sub_url).path.strip("/").upper() or "PAGE"
        if verbose:
            print(f"\n  [>]  Scraping /{path_label.lower()}...", end=" ", flush=True)

        try:
            result = extract_website(sub_url)
            if result is None:
                if verbose:
                    print("failed (Firecrawl error)")
                continue

            markdown = getattr(result, "markdown", "") or ""
            if len(markdown) < 100:
                if verbose:
                    print(f"too short ({len(markdown)} chars)")
                continue

            if verbose:
                print(f"-> {len(markdown):,} chars")

            sections.append(f"=== /{path_label} ===\n{markdown}")
            extra_pages += 1

        except Exception as e:
            if verbose:
                print(f"error: {e}")
            continue

    merged = "\n\n".join(sections)
    return merged, 1 + extra_pages  # +1 for homepage
