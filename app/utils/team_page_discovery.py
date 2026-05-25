import re
from urllib.parse import urlparse

from app.utils.crawl_queue_manager import add_to_crawl_queue
from app.logging.logging_config import pipeline_logger
from app.config.settings import (
    REJECTED_DISCOVERY_DOMAINS,
    TEAM_PAGE_PATHS,
    TEAM_PAGE_PRIORITY
)


# =========================================
# TEAM PAGE URL PATTERNS
# =========================================
# These are the most common paths VC firms
# use to display their investment team.

DEFAULT_TEAM_PAGE_PATHS = [
    "/team",
    "/people",
    "/partners",
    "/about",
    "/leadership",
    "/our-team",
    "/our-people",
    "/the-team",
    "/the-partners",
    "/investment-team",
    "/meet-the-team",
    "/about-us",
    "/who-we-are",
]


# =========================================
# TEAM PAGE PRIORITY
# =========================================
# Highest priority in the crawl queue —
# team pages are the best source for
# real partner names.

DEFAULT_TEAM_PAGE_PRIORITY = 3.5


# =========================================
# IS VALID VC WEBSITE
# =========================================

def is_valid_vc_website(website: str) -> bool:
    """
    Validate that the website URL is a
    real domain we can build team-page
    URLs from. Rejects empty, localhost,
    and generic aggregator domains.
    """

    if not website:
        return False

    website = website.strip().lower()

    # Must start with http
    if not website.startswith("http"):
        return False

    default_rejected_domains = [
        "crunchbase.com",
        "linkedin.com",
        "pitchbook.com",
        "techcrunch.com",
        "forbes.com",
        "bloomberg.com",
        "reuters.com",
        "wikipedia.org",
        "twitter.com",
        "x.com",
        "youtube.com",
        "facebook.com",
        "instagram.com",
        "medium.com",
        "substack.com",
        "angellist.com",
        "wellfound.com",
        "dealroom.co",
        "cbinsights.com",
        "sifted.eu",
        "venturebeat.com",
        "techcrunch.com",
        "seedtable.com",
        "tracxn.com",
    ]

    try:
        parsed = urlparse(website)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]

        rejected_domains = REJECTED_DISCOVERY_DOMAINS or default_rejected_domains

        for domain in rejected_domains:
            if domain in netloc:
                return False

        # Must have at least a valid TLD
        if "." not in netloc:
            return False

        return True

    except Exception:
        return False


# =========================================
# CANONICALIZE BASE URL
# =========================================

def get_base_url(website: str) -> str:
    """
    Strip path/query from website to get
    clean base domain URL.
    e.g. https://a16z.com/about -> https://a16z.com
    """
    try:
        parsed = urlparse(website.strip())
        scheme = parsed.scheme or "https"
        netloc = parsed.netloc.lower()
        if not netloc:
            return ""
        return f"{scheme}://{netloc}"
    except Exception:
        return ""


# =========================================
# DISCOVER AND QUEUE TEAM PAGES
# =========================================

def discover_team_pages(firm: str, website: str) -> int:
    """
    Given a VC firm name and its website URL,
    generate candidate team-page URLs and add
    any not-yet-crawled ones to the crawl queue
    at high priority.

    Returns the number of URLs queued.
    """

    if not firm or not website:
        return 0

    if not is_valid_vc_website(website):
        pipeline_logger.debug(
            f"Skipping team page discovery for '{firm}': "
            f"invalid/aggregator website '{website}'"
        )
        return 0

    base_url = get_base_url(website)
    if not base_url:
        return 0

    # Avoid circular import — import here
    from app.database.db import SessionLocal
    from sqlalchemy import text

    queued_count = 0

    for path in TEAM_PAGE_PATHS:

        candidate_url = f"{base_url}{path}"

        # Check if already crawled or queued
        session = SessionLocal()
        try:
            already_crawled = session.execute(
                text("SELECT id FROM crawled_urls WHERE url = :url"),
                {"url": candidate_url}
            ).fetchone()

            already_queued = session.execute(
                text("SELECT id FROM crawl_queue WHERE url = :url"),
                {"url": candidate_url}
            ).fetchone()

        finally:
            session.close()

        if already_crawled or already_queued:
            continue

        # Queue the team page at high priority
        add_to_crawl_queue(candidate_url, TEAM_PAGE_PRIORITY)

        pipeline_logger.info(
            f"Team page queued: {candidate_url} "
            f"| firm='{firm}' | priority={TEAM_PAGE_PRIORITY}"
        )

        queued_count += 1

    if queued_count > 0:
        pipeline_logger.info(
            f"Queued {queued_count} team page(s) for: '{firm}' ({base_url})"
        )

    return queued_count
