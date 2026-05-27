"""
Production validation for investor URLs, firm names, and parsed records.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from app.config.settings import (
    ALLOWED_INVESTOR_SOURCE_TYPES,
    REJECTED_DISCOVERY_DOMAINS,
    REJECTED_FIRM_NAME_EXACT,
    REJECTED_FIRM_NAME_SUBSTRINGS,
    REJECTED_URL_PATH_PATTERNS,
    RELEVANCE_MIN_CONFIDENCE,
)

# Domains that are never VC firms (publishers, platforms, tools).
_REJECTED_DOMAIN_SET = {d.lower().strip() for d in REJECTED_DISCOVERY_DOMAINS if d}

_REJECTED_FIRM_EXACT = {n.lower().strip() for n in REJECTED_FIRM_NAME_EXACT if n}

_REJECTED_FIRM_SUBSTRINGS = tuple(
    s.lower().strip() for s in REJECTED_FIRM_NAME_SUBSTRINGS if s
)

_PATH_BLOCK_RE = re.compile(
    "|".join(REJECTED_URL_PATH_PATTERNS),
    re.IGNORECASE,
) if REJECTED_URL_PATH_PATTERNS else None

_FIRM_NAME_MIN_LEN = 2
_FIRM_NAME_MAX_LEN = 120

# Legal suffixes stripped for dedup keys.
_FIRM_SUFFIX_RE = re.compile(
    r"\b(ventures?|capital|partners?|vc|llc|l\.l\.c\.|inc|corp|corporation|"
    r"holdings|advisors|advisory|management|group|fund|investments?)\b",
    re.IGNORECASE,
)

_NON_FIRM_CHARS_RE = re.compile(r"[^a-z0-9\s&\-\.']", re.IGNORECASE)


def canonicalize_url(url: str) -> str:
    if not url or not isinstance(url, str):
        return ""

    url = url.strip()

    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    try:
        parsed = urlparse(url)
        netloc = (parsed.netloc or "").lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]

        path = (parsed.path or "").rstrip("/")
        if parsed.query:
            return f"https://{netloc}{path}?{parsed.query}"
        return f"https://{netloc}{path}"
    except Exception:
        return url.strip()


def extract_domain(url: str) -> str:
    if not url:
        return ""

    try:
        parsed = urlparse(canonicalize_url(url))
        host = (parsed.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def is_rejected_url(url: str) -> bool:
    if not url or not isinstance(url, str):
        return True

    url_lower = url.lower().strip()

    if not url_lower.startswith(("http://", "https://")):
        return True

    domain = extract_domain(url)
    if not domain:
        return True

    for blocked in _REJECTED_DOMAIN_SET:
        if blocked and (domain == blocked or domain.endswith(f".{blocked}") or blocked in domain):
            return True

    if _PATH_BLOCK_RE and _PATH_BLOCK_RE.search(urlparse(url_lower).path):
        return True

    # Skip obvious non-site resources.
    if any(
        url_lower.endswith(ext)
        for ext in (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".zip", ".xml")
    ):
        return True

    return False


def is_investor_profile_url(url: str) -> bool:
    """Heuristic: URL likely belongs to a firm's own site, not a news article."""
    if is_rejected_url(url):
        return False

    url_lower = url.lower()
    positive_signals = (
        "/team",
        "/people",
        "/partners",
        "/portfolio",
        "/about",
        "/invest",
        "/thesis",
        "/companies",
        "/our-team",
        "/leadership",
    )

    if any(signal in url_lower for signal in positive_signals):
        return True

    domain = extract_domain(url)
    if domain.endswith(".vc"):
        return True

    # Root or shallow paths on non-blocked domains are acceptable VC homepages.
    path = urlparse(url_lower).path.strip("/")
    if path == "" or path.count("/") <= 1:
        return True

    return False


def normalize_firm_name(name: str) -> str:
    if not name:
        return ""

    cleaned = str(name).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip(" \"'.,;:-")

    # Strip trailing role noise sometimes parsed as firm name.
    cleaned = re.sub(
        r"\s*[-–|]\s*(team|portfolio|about|investors?|partners?|news|blog).*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    return cleaned[:_FIRM_NAME_MAX_LEN]


def normalize_firm_key(name: str) -> str:
    """Stable key for deduplication (not for display)."""
    normalized = normalize_firm_name(name).lower()
    if not normalized:
        return ""

    normalized = _FIRM_SUFFIX_RE.sub(" ", normalized)
    normalized = _NON_FIRM_CHARS_RE.sub("", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    return normalized


def is_rejected_firm_name(name: str) -> bool:
    if not name:
        return True

    cleaned = normalize_firm_name(name)
    if len(cleaned) < _FIRM_NAME_MIN_LEN:
        return True

    lower = cleaned.lower()

    if lower in _REJECTED_FIRM_EXACT:
        return True

    for substring in _REJECTED_FIRM_SUBSTRINGS:
        if substring in lower:
            return True

    # Reject names that look like URLs or domains.
    if re.search(r"https?://|www\.|\.com\b|\.org\b|\.io\b", lower):
        return True

    # Reject article-style titles.
    if len(cleaned) > 80:
        return True

    if re.search(r"\b(top|best|list of|how to|what is|guide to)\b", lower):
        return True

    # Must contain at least one letter.
    if not re.search(r"[a-zA-Z]", cleaned):
        return True

    return False


def firm_name_matches_source(firm_name: str, source_url: str, website: str = "") -> bool:
    """
    Block obvious mis-extractions (publisher name from article pages).
    Does not require literal domain == firm name (e.g. a16z.com / Andreessen Horowitz).
    """
    domain = extract_domain(source_url or website)
    if not domain:
        return True

    if is_rejected_url(source_url or website):
        return False

    firm_key = normalize_firm_key(firm_name)
    if not firm_key:
        return False

    domain_base = domain.split(".")[0].lower()

    # Always reject when firm name equals a known publisher/platform brand.
    if firm_key in {normalize_firm_key(n) for n in _REJECTED_FIRM_EXACT}:
        return False

    for substring in _REJECTED_FIRM_SUBSTRINGS:
        if substring in firm_key:
            return False

    publisher_domains = {
        "github", "forbes", "techcrunch", "bloomberg", "reuters",
        "medium", "substack", "wikipedia", "linkedin", "crunchbase",
        "pitchbook", "youtube", "twitter", "facebook", "instagram",
    }
    if domain_base in publisher_domains:
        return False

    # Article-like paths on any domain: firm name must relate to domain.
    path = urlparse(source_url or website).path.lower()
    article_path_signals = ("/news/", "/article/", "/blog/", "/stories/", "/posts/", "/tag/")
    if any(signal in path for signal in article_path_signals):
        domain_key = normalize_firm_key(domain_base.replace("-", " "))
        if domain_key and domain_key not in firm_key and firm_key not in domain_key:
            firm_tokens = firm_key.split()
            if not (firm_tokens and firm_tokens[0] == domain_key):
                return False

    return True


def resolve_website(parsed_website: str, source_url: str) -> str:
    website = canonicalize_url(parsed_website or "")
    source = canonicalize_url(source_url or "")

    if website and not is_rejected_url(website):
        return website

    if source and not is_rejected_url(source):
        parsed = urlparse(source)
        return f"https://{parsed.netloc}"

    return ""


def sanitize_parsed_investor(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize fields without rejecting the record."""
    cleaned = dict(data or {})

    cleaned["firm_name"] = normalize_firm_name(
        str(cleaned.get("firm_name", "") or "")
    )
    cleaned["website"] = resolve_website(
        str(cleaned.get("website", "") or ""),
        str(cleaned.get("source_url", "") or ""),
    )
    cleaned["source_url"] = canonicalize_url(
        str(cleaned.get("source_url", "") or "")
    )

    for field in ("focus_sectors", "investment_stage", "geography"):
        value = cleaned.get(field) or []
        if isinstance(value, list):
            cleaned[field] = list(dict.fromkeys(
                str(v).strip() for v in value if v and str(v).strip()
            ))
        else:
            cleaned[field] = []

    partners = cleaned.get("partners") or []
    if isinstance(partners, list):
        for partner in partners:
            if isinstance(partner, dict) and "confidence" not in partner:
                partner["confidence"] = 0.85

    portfolio = cleaned.get("portfolio_companies") or []
    deduped_portfolio = {}
    if isinstance(portfolio, list):
        for item in portfolio:
            if isinstance(item, dict):
                name = str(item.get("company_name", "")).strip()
                if name:
                    deduped_portfolio[name.lower()] = {
                        "company_name": name,
                        "sector": str(item.get("sector", "")).strip(),
                    }
    cleaned["portfolio_companies"] = list(deduped_portfolio.values())

    return cleaned


def validate_parsed_investor(data: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    """
    Validate a parsed investor record before save/insert.
    Returns (is_valid, reason, sanitized_data).
    """
    cleaned = sanitize_parsed_investor(data)

    firm_name = cleaned.get("firm_name", "")
    source_url = cleaned.get("source_url", "")
    website = cleaned.get("website", "")

    if not firm_name:
        return False, "missing_firm_name", cleaned

    if is_rejected_firm_name(firm_name):
        return False, "rejected_firm_name", cleaned

    if source_url and is_rejected_url(source_url):
        return False, "rejected_source_url", cleaned

    if website and is_rejected_url(website):
        cleaned["website"] = resolve_website("", source_url)
        website = cleaned.get("website", "")

    if source_url and not firm_name_matches_source(firm_name, source_url, website):
        return False, "firm_domain_mismatch", cleaned

    return True, "ok", cleaned


def should_queue_discovery_url(
    url: str,
    classification: dict[str, Any],
) -> tuple[bool, str]:
    """Gate URLs before crawl queue using classifier output."""
    if is_rejected_url(url):
        return False, "rejected_url"

    is_relevant = bool(classification.get("is_relevant"))
    confidence = float(classification.get("confidence") or 0.0)
    source_type = str(classification.get("source_type") or "unknown").strip()

    if not is_relevant:
        return False, "not_relevant"

    if confidence < RELEVANCE_MIN_CONFIDENCE:
        return False, "low_confidence"

    if source_type not in ALLOWED_INVESTOR_SOURCE_TYPES:
        return False, f"source_type_{source_type}"

    if source_type == "investor_mention":
        # Mentions are usually articles — require strong VC URL signals.
        if confidence < 0.88 and not is_investor_profile_url(url):
            return False, "mention_not_profile_url"

    return True, "ok"


def find_duplicate_investor_id(cursor, firm_name: str, website: str = "", source_url: str = "") -> int | None:
    """
    Find existing investor by exact name, normalized key, or website domain.
    """
    if not firm_name:
        return None

    cursor.execute(
        """
        SELECT id, firm_name, website
        FROM investors
        WHERE LOWER(firm_name) = LOWER(%s)
        LIMIT 1
        """,
        (firm_name,),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    firm_key = normalize_firm_key(firm_name)
    if firm_key:
        cursor.execute("SELECT id, firm_name FROM investors")
        for investor_id, existing_name in cursor.fetchall():
            if normalize_firm_key(existing_name) == firm_key:
                return investor_id

    domain = extract_domain(website or source_url)
    if domain:
        cursor.execute("SELECT id, website FROM investors WHERE website IS NOT NULL")
        for investor_id, existing_website in cursor.fetchall():
            if extract_domain(existing_website or "") == domain:
                return investor_id

    return None
