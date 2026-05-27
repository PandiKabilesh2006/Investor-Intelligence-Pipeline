import time
import requests
from functools import lru_cache
from bs4 import BeautifulSoup
from urllib.parse import urlparse


import re

# ---------------------------------------------------------------------------
# Weighted keyword configurations for precision classification
# ---------------------------------------------------------------------------

VC_WEIGHTS = {
    r"venture capital": 5,
    r"vc firm": 5,
    r"investment thesis": 5,
    r"portfolio companies": 5,
    r"backing founders": 4,
    r"seed investing": 4,
    r"series a": 4,
    r"startup investors": 4,
    r"limited partners": 4,
    r"general partners": 4,
    r"investment strategy": 4,
    r"our investments": 4,
    r"our portfolio": 4,
    r"early-stage": 3,
    r"growth stage": 3,
    r"pre-seed": 3,
    r"angel fund": 4,
    r"fund ii": 5,
    r"fund iii": 5,
    r"ventures": 2,
    r"investing in": 2,
    r"founders": 1,
    r"startups": 1,
    r"capital": 1,
    r"partner": 1,
    r"exceptional teams": 2,
    r"thesis": 1,
    r"fund": 1,
}

DIRECTORY_WEIGHTS = {
    r"investor list": 5,
    r"directory": 4,
    r"browse investors": 5,
    r"database": 3,
    r"discover vcs": 5,
    r"top investors": 4,
    r"search investors": 5,
    r"filter by": 3,
    r"compare funds": 5,
    r"investor database": 5,
}

BLOG_WEIGHTS = {
    r"published on": 4,
    r"written by": 4,
    r"read more": 3,
    r"comments section": 5,
    r"subscribe to newsletter": 4,
    r"author bio": 5,
    r"posted in": 4,
}

STARTUP_WEIGHTS = {
    r"book demo": 5,
    r"free trial": 5,
    r"pricing plans": 5,
    r"customers": 2,
    r"sales software": 4,
    r"crm tool": 4,
    r"get started": 3,
    r"sign up for free": 5,
    r"try for free": 5,
    r"cancel anytime": 5,
    r"create account": 4,
    r"developers": 2,
    r"api documentation": 4,
    r"financial infrastructure": 3,
    r"payment processing": 4,
    r"platform": 1,
    r"payments": 1,
}

DIRECTORY_DOMAINS = {
    # Known VC aggregator / directory sites
    "openvc.app", "saasvclist.com", "crunchbase.com", "pitchbook.com",
    "tracxn.com", "superscout.co", "angellist.com", "signal.nfx.com",
    "vcguide.co", "venturescanner.com", "vclist.co",
    "vcsheet.com", "shizune.co", "basetemplates.com",
    "fundz.net", "dealroom.co", "f6s.com", "svb.com", "smergers.com",
}

# Hard-block: known media, news, and general-purpose sites that will
# never be a VC firm but score high on VC keywords in articles.
MEDIA_DOMAINS = {
    "forbes.com", "techcrunch.com", "medium.com", "hbr.org",
    "venturebeat.com", "wsj.com", "bloomberg.com", "reuters.com",
    "businessinsider.com", "inc.com", "entrepreneur.com",
    "wired.com", "theverge.com", "ft.com", "cnbc.com",
    "nytimes.com", "economist.com", "axios.com",
    "sifted.eu", "eu-startups.com", "startupdaily.net",
}

# ---------------------------------------------------------------------------
# Domain-level cache so the same base domain is never re-fetched
import os
import json

# ---------------------------------------------------------------------------
# Persistent domain classification cache setup
# ---------------------------------------------------------------------------
_CACHE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    ".cache",
    "verifier_cache.json"
)
os.makedirs(os.path.dirname(_CACHE_FILE), exist_ok=True)

_domain_cache: dict = {}
if os.path.exists(_CACHE_FILE):
    try:
        with open(_CACHE_FILE, "r", encoding="utf-8") as f:
            _domain_cache = json.load(f)
    except:
        _domain_cache = {}


def _save_domain_cache():
    try:
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_domain_cache, f, indent=2)
    except:
        pass


def _update_domain_cache(domain: str, classification: str):
    _domain_cache[domain] = classification
    _save_domain_cache()


def _base_domain(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def _extract_page_text(url: str) -> str:
    """Fetch and return lowercased plain text from a URL."""
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
            return ""
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return soup.get_text(" ", strip=True).lower()

    except requests.exceptions.Timeout:
        print("  ⚠️  Verifier: page fetch timed out")
        return ""
    except Exception as e:
        print(f"  ⚠️  Verifier: page fetch failed ({type(e).__name__})")
        return ""


def _calculate_weighted_score(text: str, weights: dict) -> int:
    """Calculate the cumulative score of matching keywords using word boundary regex."""
    score = 0
    for pattern, weight in weights.items():
        # Match using word boundaries to prevent false substring matches (e.g. matching "vc" inside other letters)
        if re.search(rf"\b{pattern}\b", text):
            score += weight
    return score


def classify_website(url: str) -> str:
    """
    Classify website type to filter out non-VC sites using a weighted regex scoring system.

    Returns one of:
      "vc_firm"   — legitimate VC firm website
      "directory" — investor directory / database
      "blog"      — blog or news site
      "startup"   — startup / SaaS product
      "unknown"   — cannot classify or insufficient data
    """
    url_lower = url.lower()

    # 1a. Known directory domains — fast path
    domain = _base_domain(url)
    if any(blocked in domain for blocked in DIRECTORY_DOMAINS):
        return "directory"

    # 1b. Known media / news domains — fast path
    if any(blocked in domain for blocked in MEDIA_DOMAINS):
        return "blog"

    # 2. Domain-level cache — avoid re-fetching the same site
    if domain in _domain_cache:
        return _domain_cache[domain]

    # 3. Fetch and score
    text = _extract_page_text(url)

    if not text or len(text) < 100:
        # Fallback: If HTTP fetch failed/blocked (e.g. Cloudflare 403), check if the domain 
        # itself has strong VC indicators. This ensures we don't drop high-quality VCs.
        domain_indicators = ["ventures", "capital", "partners", "equity", "seed", "fund", "invest", "vc"]
        if any(ind in domain for ind in domain_indicators):
            _update_domain_cache(domain, "vc_firm")
            return "vc_firm"
        _update_domain_cache(domain, "unknown")
        return "unknown"

    vc_score        = _calculate_weighted_score(text, VC_WEIGHTS)
    directory_score = _calculate_weighted_score(text, DIRECTORY_WEIGHTS)
    blog_score      = _calculate_weighted_score(text, BLOG_WEIGHTS)
    startup_score   = _calculate_weighted_score(text, STARTUP_WEIGHTS)

    scores = {
        "vc_firm":   vc_score,
        "directory": directory_score,
        "blog":      blog_score,
        "startup":   startup_score,
    }

    best = max(scores, key=scores.get)
    best_score = scores[best]

    # Require at least 5 points to be classified with confidence
    if best_score < 5:
        result = "unknown"
    # Tie-breakers: default to non-VC if scores are tied, to save credits
    elif directory_score >= vc_score and directory_score >= 5:
        result = "directory"
    elif startup_score >= vc_score and startup_score >= 5:
        result = "startup"
    elif blog_score >= vc_score and blog_score >= 5:
        result = "blog"
    else:
        result = best

    _update_domain_cache(domain, result)
    return result