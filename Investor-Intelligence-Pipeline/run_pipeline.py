"""
Investor Intelligence Pipeline -- Main Entry Point

Run:
    python run_pipeline.py

Optional env var:
    OLLAMA_MODEL=qwen2.5:7b python run_pipeline.py
"""

import warnings
import json
import sys
import os
import io
from datetime import datetime

# Ensure UTF-8 output on Windows (avoids UnicodeEncodeError for special chars)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse

warnings.filterwarnings("ignore")

from app.search.tavily_search import search_investors
from app.resolution.resolver import resolve_official_website
from app.verification.verifier import classify_website
from app.extraction.firecrawl_extract import extract_website
from app.extraction.multi_page import scrape_and_merge
from app.utils.cleaner import clean_content, DEFAULT_MAX_CHARS_GROQ, DEFAULT_MAX_CHARS_OLLAMA
from app.utils.directory_miner import mine_directory_links
from app.parsing.gpt_parser import parse_investor
from app.output.formatter import format_investor, MAX_CONFIDENCE
from app.output.exporter import export_to_csv
from app.enrichment.email_guesser import generate_guessed_emails
from app.config.settings import OLLAMA_MODEL, GROQ_API_KEY, PARSER_BACKEND, GROQ_MODEL


def _active_backend_label() -> str:
    """Human-readable description of the active LLM backend."""
    if PARSER_BACKEND == "ollama":
        return f"Ollama ({OLLAMA_MODEL})"
    if PARSER_BACKEND == "groq":
        return f"Groq ({GROQ_MODEL})"
    # auto
    if GROQ_API_KEY:
        return f"Groq ({GROQ_MODEL}) -> Ollama fallback"
    return f"Ollama ({OLLAMA_MODEL}) [no Groq key]"

# ============================================================
# QUERY PRESETS
# ============================================================

QUERY_PRESETS = {
    "1": {
        "name": "AI & Machine Learning VCs",
        "queries": [
            "AI venture capital fund portfolio investments",
            "machine learning VC firm portfolio companies",
            "AI infrastructure seed fund general partners",
            "artificial intelligence early stage venture fund team",
        ],
    },
    "2": {
        "name": "Enterprise SaaS Investors",
        "queries": [
            "enterprise AI venture capital fund portfolio",
            "B2B SaaS seed fund general partners investments",
            "enterprise software VC firm portfolio companies",
            "SaaS growth stage venture fund investments",
        ],
    },
    "3": {
        "name": "Developer Tools & Infrastructure",
        "queries": [
            "developer tools seed fund portfolio investments",
            "devtools venture capital firm team partners",
            "infrastructure VC fund portfolio companies",
            "cloud infrastructure venture fund investments",
        ],
    },
    "4": {
        "name": "Voice AI & Conversational AI",
        "queries": [
            "voice AI venture fund portfolio companies",
            "conversational AI seed fund investments",
            "speech technology VC firm portfolio",
            "AI voice startup venture capital partners",
        ],
    },
    "5": {
        "name": "Fintech & Financial Services",
        "queries": [
            "fintech venture capital fund portfolio companies",
            "financial services VC firm investments",
            "payment technology seed fund portfolio",
            "banking technology venture fund general partners",
        ],
    },
    "6": {
        "name": "Healthcare & Biotech",
        "queries": [
            "healthcare venture capital fund portfolio investments",
            "biotech seed fund general partners",
            "digital health VC firm portfolio companies",
            "medical technology venture fund team",
        ],
    },
    "7": {
        "name": "India & South Asia VCs",
        "queries": [
            "India venture capital fund portfolio companies",
            "Indian startup seed fund general partners investments",
            "India early stage VC firm portfolio",
            "South Asia venture capital fund team investments",
        ],
    },
    "8": {
        "name": "Custom Query",
        "queries": [],  # filled at runtime
    },
}

# ============================================================
# CONFIGURATION
# ============================================================

MIN_CONTENT_LENGTH = 300  # Min chars of extracted markdown
MAX_DIRECTORY_MINES = 3   # Max directory pages to mine for VC links
# Sub-pages to scrape per firm (each costs 1 Firecrawl credit).
# Targets /team and /portfolio first. Set to 0 to disable multi-page scraping.
MAX_SUB_PAGES = 2

# Websites to skip before any expensive API call
_SKIP_URL_DOMAINS = {
    "linkedin.com", "twitter.com", "x.com", "facebook.com",
    "crunchbase.com", "pitchbook.com", "angellist.com",
    "wellfound.com", "tracxn.com",
    # Media / news
    "forbes.com", "techcrunch.com", "medium.com", "hbr.org",
    "venturebeat.com", "wsj.com", "bloomberg.com", "reuters.com",
    "businessinsider.com", "wired.com", "theverge.com", "cnbc.com",
    "nytimes.com", "axios.com", "sifted.eu",
    # VC directories — already caught by verifier but skip early
    "vcsheet.com", "shizune.co", "basetemplates.com",
    "openvc.app", "dealroom.co", "f6s.com",
}
_SKIP_URL_PATTERNS = [
    "/blog/", "/news/", "/article/", "/post/", "/author/",
    "/insights/", "/resources/", "/reports/", "/press/",
    "/podcast/", "/webinar/", "/event/",
]

# Website types classified by verifier that should be skipped
_SKIP_WEBSITE_TYPES = {"unknown", "directory", "blog", "startup"}

# ============================================================
# CONFIDENCE SCORE
# ============================================================

# Individual field weights — must total to MAX_CONFIDENCE_SCORE
MAX_CONFIDENCE_SCORE = 19  # increased for new fields

def calculate_confidence_score(investor: Dict) -> int:
    """
    Score how complete / reliable the extracted investor record is.
    Returns an integer 0–MAX_CONFIDENCE_SCORE.
    """
    score = 0

    firm = investor.get("firm", "")
    if firm and len(firm) > 3:
        score += 3

    website = investor.get("website", "")
    if website and _is_valid_url(website):
        score += 2

    thesis = investor.get("thesis", "").strip()
    if thesis and len(thesis) > 20:
        score += 1                          # new field

    focus = investor.get("focus_sectors", [])
    if focus:
        score += 2

    stage = investor.get("investment_stage", [])
    if stage:
        score += 1

    partners = investor.get("partners", [])
    if partners:
        score += 2

    portfolio = investor.get("portfolio_companies", [])
    if len(portfolio) >= 3:
        score += 2
    elif portfolio:
        score += 1

    geography = investor.get("geography", [])
    if geography:
        score += 1

    contact = investor.get("contact_links", [])
    if contact:
        score += 1

    # New fields
    if investor.get("fund_number", "").strip():
        score += 1
    if investor.get("fund_size", "").strip():
        score += 1
    if investor.get("active_status", "").strip():
        score += 1
    if investor.get("pitch_process", "").strip():
        score += 1

    return min(score, MAX_CONFIDENCE_SCORE)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _is_valid_url(url: str) -> bool:
    try:
        r = urlparse(url)
        return bool(r.scheme and r.netloc)
    except Exception:
        return False


def _should_skip_url(url: str) -> bool:
    """Fast pre-filter before any API call."""
    url_lower = url.lower()
    if any(d in url_lower for d in _SKIP_URL_DOMAINS):
        return True
    if any(p in url_lower for p in _SKIP_URL_PATTERNS):
        return True
    return False


def _normalize_firm_name(name: str) -> str:
    """Lowercase + strip for deduplication comparison."""
    return name.strip().lower()


def display_menu() -> Tuple[str, str, Optional[str]]:
    w = 62
    print("\n" + "=" * w)
    print("  INVESTOR INTELLIGENCE PIPELINE".center(w))
    print("=" * w)
    print(f"  Parser : {_active_backend_label()}")
    print("-" * w)
    print("\n  Select a query preset (or type a custom search, e.g., 'AI deeptech in India'):\n")
    for key, preset in QUERY_PRESETS.items():
        print(f"    [{key}]  {preset['name']}")
    print("\n" + "-" * w)
    while True:
        user_input = input("\n  Enter choice or query: ").strip()
        if not user_input:
            continue
        if user_input in QUERY_PRESETS:
            return user_input, "", None
        
        # It's a free-text query! Let's auto-route it.
        try:
            from app.utils.router import route_query_to_preset
            choice, geo, name = route_query_to_preset(user_input)
            print(f"\n  [ROUTER] Auto-matched your query to preset: \"{name}\"")
            if geo:
                print(f"  [ROUTER] Extracted geography filter: \"{geo}\"")
            return choice, geo, user_input
        except Exception as e:
            print(f"  [!] Routing failed: {e}. Please select 1-8.")


def get_queries(choice: str, typed_query: Optional[str] = None) -> List[str]:
    preset = QUERY_PRESETS[choice]
    if choice == "8":
        if typed_query:
            return [typed_query]
        print("\n  [?]  Enter queries (one per line, blank line to finish):")
        queries: list[str] = []
        while True:
            q = input("  > ").strip()
            if not q:
                break
            queries.append(q)
        if not queries:
            print("  [!]  No queries entered -- using default.")
            queries = ["AI venture capital firms"]
        return queries
    print(f"\n  [+]  Selected: {preset['name']}")
    print(f"  [i]  Queries:  {len(preset['queries'])}")
    return preset["queries"]


def get_geography_filter(default_geo: str = "") -> str:
    """
    Optionally ask the user to narrow results to a specific geography.
    Returns the geography string (e.g. "India", "Chennai", "Southeast Asia")
    or empty string if the user skips.
    """
    print("\n" + "-" * 62)
    print("  [GEO]  Geography filter  (optional)")
    print("         Examples: India, Chennai, Southeast Asia, Europe, US")
    if default_geo:
        geo = input(f"         Enter location or press Enter to keep [{default_geo}]: ").strip()
        if not geo:
            geo = default_geo
    else:
        geo = input("         Enter location or press Enter to skip: ").strip()
    if geo:
        print(f"  [+]  Geography filter: {geo}")
    else:
        print("  [i]  No geography filter -- searching globally")
    return geo


def apply_geography(queries: List[str], geography: str) -> List[str]:
    """
    Append the geography term to every query so Tavily returns
    region-specific results.
    Also adds a dedicated set of discovery queries to boost volume.
    """
    if not geography:
        # Add massive set of broad global discovery queries
        broad_global_queries = [
            "venture capital fund portfolio companies",
            "startup investors seed fund general partners",
            "top early stage VC firms",
            "technology venture capital funds",
            "list of active seed investors",
            "leading VC funds investing in startups",
            "angel network and venture capital",
            "new venture capital funds launched"
        ]
        queries.extend(broad_global_queries)
        return queries
        
    geo_queries = [f"{q} {geography}" for q in queries]
    
    # Add a massive set of broad discovery queries to force Tavily to return huge volume
    broad_queries = [
        f"{geography} venture capital fund portfolio companies",
        f"{geography} startup investors seed fund general partners",
        f"top early stage VC firms in {geography}",
        f"{geography} technology venture capital funds",
        f"list of active seed investors {geography}",
        f"leading {geography} VC funds investing in startups",
        f"{geography} angel network and venture capital",
        f"new venture capital funds launched in {geography}"
    ]
    geo_queries.extend(broad_queries)
    return geo_queries


def get_process_limit(total_available: int) -> int:
    """
    Ask how many URLs to process.
    Returns the limit as an integer, or total_available for 'all'.

    Note: each URL that passes filtering costs 1 Firecrawl credit.
    Most URLs are rejected before Firecrawl (blocked domain, wrong site
    type, content too short), so the real credit spend is much lower
    than the number of URLs you say yes to here.
    """
    print("\n" + "-" * 62)
    print(f"  [LIMIT]  {total_available} unique URLs queued for processing")
    print("           Each URL that passes filtering = 1 Firecrawl credit.")
    print("           In practice ~30-50% are filtered before Firecrawl.")
    print("           Press Enter to process ALL, or type a number to cap.")

    while True:
        raw = input("           Process limit (Enter = all): ").strip()
        if not raw:
            print(f"  [+]  Processing all {total_available} URLs")
            return total_available
        try:
            n = int(raw)
            if n <= 0:
                print("  [!]  Please enter a positive number.")
                continue
            skipped = max(0, total_available - n)
            print(f"  [+]  Processing top {n} URLs")
            if skipped:
                print(f"  [i]  {skipped} URL(s) will be skipped "
                      f"(run again with more to catch them)")
            return min(n, total_available)
        except ValueError:
            print("  [!]  Enter a number or press Enter for all.")


# ============================================================
# PER-RESULT PROCESSOR
# ============================================================

def process_single_result(result: Dict, index: int, total: int) -> Optional[Dict]:
    """
    Full pipeline for a single search result URL.
    Returns a structured investor dict or None if the URL should be skipped.
    """
    raw_url = result.get("url", "")

    print(f"\n{'─' * 62}")
    print(f"  [{index}/{total}]  {raw_url}")
    print(f"{'─' * 62}")

    if not raw_url or not _is_valid_url(raw_url):
        print("  [!]  Invalid URL — skipping")
        return None

    if _should_skip_url(raw_url):
        print("  [!]  Blocked domain/pattern — skipping")
        return None

    # ── Step 1: Resolve official homepage ───────────────────────────────
    print("  [>]  Resolving homepage…", end=" ", flush=True)
    resolved_url = resolve_official_website(raw_url)
    if not resolved_url:
        print("failed")
        return None
    print(f"→  {resolved_url}")

    # ── Step 2: Classify website type ────────────────────────────────────
    print("  [?]  Classifying site…", end=" ", flush=True)
    website_type = classify_website(resolved_url)
    print(f"→  {website_type}")

    if website_type in _SKIP_WEBSITE_TYPES:
        print(f"  [!]  Skipping ({website_type})")
        return None

    # ── Step 3: Extract homepage content ────────────────────────────────
    print("  [+]  Extracting content...", end=" ", flush=True)
    website_data = extract_website(resolved_url)

    if website_data is None:
        print("failed (Firecrawl error)")
        return None

    markdown_content = getattr(website_data, "markdown", "") or ""

    if not markdown_content:
        print("failed (empty response)")
        return None

    if len(markdown_content) < MIN_CONTENT_LENGTH:
        print(f"too short ({len(markdown_content)} chars)")
        return None

    print(f"-> {len(markdown_content):,} chars")

    # ── Step 3.5: Scrape sub-pages (team, portfolio, about) ─────────────
    if MAX_SUB_PAGES > 0:
        merged_content, total_pages = scrape_and_merge(
            homepage_url=resolved_url,
            homepage_markdown=markdown_content,
            max_sub_pages=MAX_SUB_PAGES,
            verbose=True,
        )
        if total_pages > 1:
            print(f"  [+]  Merged {total_pages} pages: {len(merged_content):,} chars total")
    else:
        merged_content = markdown_content
        total_pages = 1

    # ── Step 4: Clean content ────────────────────────────────────────────
    # Use a larger window for Groq (70B handles it); smaller for Ollama
    is_groq_active = GROQ_API_KEY and PARSER_BACKEND in ("groq", "auto")
    max_chars = DEFAULT_MAX_CHARS_GROQ if is_groq_active else DEFAULT_MAX_CHARS_OLLAMA

    print(f"  [~]  Cleaning content...", end=" ", flush=True)
    cleaned_content = clean_content(merged_content, max_chars=max_chars)

    if not cleaned_content or len(cleaned_content) < 80:
        print("insufficient relevant content after cleaning")
        return None

    print(f"-> {len(cleaned_content):,} chars retained")

    # ── Step 5: Parse with LLM ──────────────────────────────────────────
    print(f"  [*]  Parsing...", end=" ", flush=True)
    parsed_data = parse_investor(cleaned_content)

    firm = parsed_data.get("firm", "")
    if not firm or len(firm) < 3:
        print("no valid firm extracted")
        return None

    backend_used = parsed_data.pop("_parser", "?")
    print(f"->  {firm}  [{backend_used}]")

    # ── Step 6: Score ────────────────────────────────────────────────────
    score = calculate_confidence_score(parsed_data)
    parsed_data["confidence_score"] = score
    parsed_data["source_url"] = resolved_url
    parsed_data["extracted_at"] = datetime.utcnow().isoformat() + "Z"
    parsed_data["pages_scraped"] = total_pages

    print(f"  [i]  Confidence: {score}/{MAX_CONFIDENCE_SCORE}  ({total_pages} page(s) scraped)")
    return parsed_data


def get_category_slug(choice: str) -> str:
    """Clean the query preset name to create a safe filename slug."""
    if choice == "8":
        return "custom"
    name = QUERY_PRESETS.get(choice, {}).get("name", "unknown")
    clean = name.lower()
    for char in [" & ", " and ", " ", "/", "\\"]:
        clean = clean.replace(char, "_")
    # Keep only alphanumeric and underscores
    slug = "".join(c for c in clean if c.isalnum() or c == "_")
    # Clean trailing/multiple underscores
    while "__" in slug:
        slug = slug.replace("__", "_")
    slug = slug.strip("_")
    # Strip trailing vcs or investors for cleaner filenames
    if slug.endswith("_vcs"):
        slug = slug[:-4]
    elif slug.endswith("_investors"):
        slug = slug[:-10]
    return slug


# ============================================================
# MAIN PIPELINE
# ============================================================

def check_cache_and_prompt(category_slug: str, db_active: bool, master_json_file: str) -> Optional[List[dict]]:
    """
    Check if database or master JSON has >= 15 records for the category.
    If yes, prompt the user to load cached data.
    Returns the list of cached investor dicts if they choose to load, else None.
    """
    cached_investors = []
    source_label = ""
    
    # Try DB first
    if db_active:
        try:
            from app.database.operations import get_cached_investor_count, get_cached_investors_by_category
            db_count = get_cached_investor_count(category_slug)
            if db_count >= 15:
                cached_investors = get_cached_investors_by_category(category_slug)
                source_label = "database"
        except Exception as e:
            print(f"  [DATABASE] Failed to check database cache: {e}")
            
    # Fall back to master JSON file if DB didn't have >= 15
    if len(cached_investors) < 15 and os.path.exists(master_json_file):
        try:
            with open(master_json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) >= 15:
                    cached_investors = data
                    source_label = f"local JSON master file ({master_json_file})"
        except Exception:
            pass
            
    if len(cached_investors) >= 15:
        print(f"\n  [DATABASE CACHE] Found {len(cached_investors)} existing VC firms for this category in {source_label}!")
        print("                   Would you like to load this data instantly instead of a fresh crawl?")
        print("                   [1] Yes, load instantly (saves API credits & time)")
        print("                   [2] No, run a fresh web search to discover brand-new leads")
        while True:
            ans = input("\n                   Choice (1-2): ").strip()
            if ans == "1":
                print("\n  [+] Loading cached investors instantly...")
                return cached_investors
            elif ans == "2":
                print("\n  [+] Skipping cache -- proceeding with fresh web search.")
                return None
            print("  [!] Invalid choice. Please enter 1 or 2.")
    return None


def main():
    # Initialize database
    db_active = False
    try:
        from app.database.connection import init_db
        db_active = init_db()
    except Exception as e:
        print(f"  [DATABASE] Failed to initialize database: {e}")

    choice, geo_from_query, typed_query = display_menu()
    queries = get_queries(choice, typed_query)
    geography = get_geography_filter(geo_from_query)
    queries = apply_geography(queries, geography)

    if not queries:
        print("  [!]  No queries. Exiting.")
        sys.exit(1)

    # Get preset category slug for segmented databases
    category_slug = get_category_slug(choice)
    master_json_file = f"investors_{category_slug}.json"
    master_csv_file = f"investors_{category_slug}.csv"

    # Caching check
    cached_data = check_cache_and_prompt(category_slug, db_active, master_json_file)
    if cached_data is not None:
        source_label = "database" if db_active and len(cached_data) >= 15 else f"local JSON master file ({master_json_file})"
        # Apply geography filter to cached data if set
        if geography:
            geo_lower = geography.lower()
            filtered = []
            for inv in cached_data:
                inv_geos = inv.get("geography", [])
                if isinstance(inv_geos, list):
                    if any(geo_lower in str(g).lower() for g in inv_geos):
                        filtered.append(inv)
                elif isinstance(inv_geos, str):
                    if geo_lower in inv_geos.lower():
                        filtered.append(inv)
            print(f"  [+] Filtered cached results by geography '{geography}': {len(cached_data)} -> {len(filtered)} firms.")
            cached_data = filtered
            
        final_investors = cached_data
        
        # Phase 6: Display
        print(f"\n{'=' * 62}")
        print("  PHASE 6 -- RESULTS DISPLAY")
        print(f"{'=' * 62}")
        if not final_investors:
            print("  [!] No valid investors found in cache matching the geography filter.")
            sys.exit(0)
            
        page_size = 5
        for i in range(0, len(final_investors), page_size):
            chunk = final_investors[i:i + page_size]
            for idx, investor in enumerate(chunk):
                rank = i + idx + 1
                print(f"\n  +-- RANK #{rank} {'--' + '-' * 48}")
                print(format_investor(investor))
                
            if i + page_size < len(final_investors):
                try:
                    next_end = min(i + page_size * 2, len(final_investors))
                    input(f"\n  [Press Enter to view results {i + page_size + 1} to {next_end}]...")
                except (KeyboardInterrupt, EOFError):
                    print("\n  [!] Display aborted by user. Saving results...")
                    break
                    
        # Phase 7: Save transactional records
        print(f"\n{'=' * 62}")
        print("  SAVING RESULTS (FROM CACHE)")
        print(f"{'=' * 62}")
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        geo_slug = geography.lower().replace(" ", "_") if geography else "global"
        output_file = f"investors_{category_slug}_{geo_slug}_{timestamp}.json"
        csv_file = f"investors_{category_slug}_{geo_slug}_{timestamp}.csv"
        
        # Enrich with guessed emails
        generate_guessed_emails(final_investors)
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(final_investors, f, indent=2, ensure_ascii=False)
        export_to_csv(final_investors, csv_file)
        
        print(f"  [+] Saved {len(final_investors)} cached investors to transactional logs")
        print(f"  [>] {output_file}")
        print(f"  [>] {csv_file}")
        
        # Summary
        print(f"\n{'=' * 62}")
        print("  PIPELINE SUMMARY (LOADED FROM CACHE)")
        print(f"{'=' * 62}")
        avg_score = (
            sum(inv.get("confidence_score", 0) for inv in final_investors)
            / len(final_investors)
            if final_investors else 0
        )
        rows = [
            ("Source",              source_label),
            ("Geography filter",    geography if geography else "Global (none set)"),
            ("Unique firms loaded", len(final_investors)),
            ("Avg confidence",      f"{avg_score:.1f}/{MAX_CONFIDENCE}"),
            ("Output file",         output_file),
        ]
        for label, value in rows:
            print(f"  {label:<24}  {value}")
        print(f"\n{'=' * 62}")
        print("  PIPELINE COMPLETE")
        print(f"{'=' * 62}\n")
        return

    # Load all already-processed domains (both successful VCs and rejected/unknown ones)
    # on startup to feed into Tavily's exclude list, forcing it to discover brand-new websites!
    existing_domains = set()
    
    # 1. Load from successful master preset-specific database
    if os.path.exists(master_json_file):
        try:
            with open(master_json_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                if isinstance(existing_data, list):
                    for inv in existing_data:
                        web = inv.get("website", "")
                        if web:
                            domain = urlparse(web).netloc.lower()
                            if domain.startswith("www."):
                                domain = domain[4:]
                            if domain:
                                existing_domains.add(domain)
        except Exception:
            pass

    # 1.5 Load existing domains from DB if active
    if db_active:
        try:
            from app.database.operations import get_existing_domains_from_db
            db_domains = get_existing_domains_from_db()
            if db_domains:
                existing_domains.update(db_domains)
                print(f"  [DATABASE] Loaded {len(db_domains)} domains from database for Smart Discovery.")
        except Exception as e:
            print(f"  [DATABASE] Failed to load domains from DB: {e}")

    # 2. Load from verifier persistent cache (to exclude junk/non-VC domains too!)
    verifier_cache_file = os.path.join(".cache", "verifier_cache.json")
    if os.path.exists(verifier_cache_file):
        try:
            with open(verifier_cache_file, "r", encoding="utf-8") as f:
                ver_cache = json.load(f)
                if isinstance(ver_cache, dict):
                    for domain in ver_cache.keys():
                        existing_domains.add(domain)
        except Exception:
            pass

    if existing_domains:
        print(f"  [+]  Smart Discovery: Loaded {len(existing_domains)} domains to exclude from search results.")

    # ── Phase 1: Search ─────────────────────────────────────────────────
    print(f"\n{'=' * 62}")
    print("  PHASE 1 -- SEARCHING")
    print(f"{'=' * 62}")

    all_results: list[dict] = []
    for i, query in enumerate(queries, 1):
        print(f"\n  [{i}/{len(queries)}]  \"{query}\"")
        search_results = search_investors(query, exclude_domains=list(existing_domains))
        results = search_results.get("results", [])
        all_results.extend(results)
        print(f"  [+]  {len(results)} results")

    print(f"\n  Total raw results: {len(all_results)}")

    # ── Phase 2: Deduplicate URLs ────────────────────────────────────────
    print(f"\n{'=' * 62}")
    print("  PHASE 2 -- DEDUPLICATING")
    print(f"{'=' * 62}")

    seen_urls: set[str] = set()
    deduplicated: list[dict] = []
    skipped_existing = 0

    for result in all_results:
        url = result.get("url", "")
        if not url:
            continue
        
        # Smart Skip: Avoid processing domains we already have in our master database
        try:
            domain = urlparse(url).netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            if domain in existing_domains:
                skipped_existing += 1
                continue
        except:
            pass

        key = url.lower().rstrip("/")
        if key not in seen_urls:
            seen_urls.add(key)
            deduplicated.append(result)

    print(f"  [+]  {len(all_results)} -> {len(deduplicated)} unique URLs")
    if skipped_existing > 0:
        print(f"  [+]  Smart Skip: Filtered out {skipped_existing} URLs already fully processed in previous runs.")

    # ── Phase 2.5: Directory Mining ──────────────────────────────────────
    # Extract real VC firm URLs from any directory pages Tavily returned,
    # instead of discarding them entirely.
    print(f"\n{'=' * 62}")
    print("  PHASE 2.5 -- MINING DIRECTORIES")
    print(f"{'=' * 62}")

    from app.verification.verifier import DIRECTORY_DOMAINS, _base_domain as _vbase
    directory_results = [
        r for r in deduplicated
        if any(d in _vbase(r.get("url", "")) for d in DIRECTORY_DOMAINS)
    ]

    mined_count = 0
    if directory_results:
        print(f"  Found {len(directory_results)} directory page(s) to mine")
        for dir_result in directory_results[:MAX_DIRECTORY_MINES]:
            dir_url = dir_result.get("url", "")
            print(f"  [>]  Mining: {dir_url}")
            mined_urls = mine_directory_links(dir_url)
            added = 0
            for mined_url in mined_urls:
                key = mined_url.lower().rstrip("/")
                if key not in seen_urls and not _should_skip_url(mined_url):
                    # Smart Skip check for mined directory links too!
                    try:
                        domain = urlparse(mined_url).netloc.lower()
                        if domain.startswith("www."):
                            domain = domain[4:]
                        if domain in existing_domains:
                            skipped_existing += 1
                            continue
                    except:
                        pass

                    seen_urls.add(key)
                    deduplicated.append({"url": mined_url, "source": "directory_mining"})
                    added += 1
                    mined_count += 1
            print(f"  [+]  Added {added} new VC URLs from this directory")
        if mined_count:
            print(f"  [+]  Total new URLs added: {mined_count}")
        
        # Remove the directory URLs from deduplicated so we don't try to scrape them as VC firms
        deduplicated = [r for r in deduplicated if r not in directory_results]
    else:
        print("  [i]  No known directory pages in results -- skipping")

    # ── Phase 3: Process with Auto-Resume ────────────────────────────────
    print(f"\n{'=' * 62}")
    print("  PHASE 3 -- PROCESSING")
    print(f"{'=' * 62}")

    process_limit = get_process_limit(len(deduplicated))
    to_process = deduplicated[:process_limit]
    
    # Checkpoint setup
    CHECKPOINT_FILE = os.path.join(".cache", "pipeline_checkpoint.json")
    os.makedirs(".cache", exist_ok=True)

    raw_investors: list[dict] = []
    processed_urls: set[str] = set()

    # Load checkpoint if it exists
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                checkpoint = json.load(f)
                # Verify it is for the same query/geography run to avoid mixing states
                if checkpoint.get("geography") == geography and checkpoint.get("query_count") == len(queries):
                    raw_investors = checkpoint.get("raw_investors", [])
                    processed_urls = set(checkpoint.get("processed_urls", []))
                    print(f"  [+]  Found checkpoint! Restoring {len(processed_urls)} processed URLs.")
                else:
                    print("  [i]  Existing checkpoint belongs to a different search preset. Starting fresh.")
        except Exception as e:
            print(f"  [!]  Error loading checkpoint: {e}. Starting fresh.")

    remaining_to_process = [r for r in to_process if r.get("url", "").lower().rstrip("/") not in processed_urls]
    
    if len(remaining_to_process) < len(to_process):
        print(f"  [>]  Resuming: {len(remaining_to_process)} URLs left to process out of {len(to_process)}.")
    else:
        print(f"\n  Starting processing of {len(to_process)} URLs...")

    try:
        for idx, result in enumerate(remaining_to_process, 1):
            url = result.get("url", "")
            data = process_single_result(result, len(processed_urls) + idx, len(to_process))
            
            if data:
                raw_investors.append(data)
                print(f"  [+]  Added: {data.get('firm')}")
            
            # Save checkpoint
            if url:
                processed_urls.add(url.lower().rstrip("/"))
                
            try:
                with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
                    json.dump({
                        "geography": geography,
                        "query_count": len(queries),
                        "raw_investors": raw_investors,
                        "processed_urls": list(processed_urls)
                    }, f, indent=2, ensure_ascii=False)
            except Exception as e:
                pass # Don't crash the pipeline if writing checkpoint fails

    except (KeyboardInterrupt, SystemExit):
        print(f"\n\n  [!]  Pipeline execution paused by user. Progress saved ({len(processed_urls)}/{len(to_process)} processed).")
        print("       Run the pipeline again with the same preset to resume!")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n  [❌]  Pipeline crashed: {e}. Progress saved ({len(processed_urls)}/{len(to_process)} processed).")
        sys.exit(0)

    # Success! Clean up checkpoint file
    if os.path.exists(CHECKPOINT_FILE):
        try:
            os.remove(CHECKPOINT_FILE)
        except:
            pass

    # ── Phase 4: Firm-name deduplication ─────────────────────────────────
    print(f"\n{'=' * 62}")
    print("  PHASE 4 -- DEDUPLICATING FIRMS")
    print(f"{'=' * 62}")

    seen_firms: set[str] = set()
    final_investors: list[dict] = []
    for inv in raw_investors:
        key = _normalize_firm_name(inv.get("firm", ""))
        if key and key not in seen_firms:
            seen_firms.add(key)
            final_investors.append(inv)
        elif key in seen_firms:
            print(f"  [~]  Duplicate firm: {inv.get('firm')} -- skipping")

    print(f"  [+]  {len(raw_investors)} -> {len(final_investors)} unique firms")

    # ── Phase 5: Sort by confidence ──────────────────────────────────────
    final_investors.sort(key=lambda x: x.get("confidence_score", 0), reverse=True)

    # ── Phase 6: Display ─────────────────────────────────────────────────
    print(f"\n{'=' * 62}")
    print("  PHASE 6 -- RESULTS DISPLAY")
    print(f"{'=' * 62}")

    if not final_investors:
        print("  [!]  No valid investors found.")
        sys.exit(0)

    page_size = 5
    for i in range(0, len(final_investors), page_size):
        chunk = final_investors[i:i + page_size]
        for idx, investor in enumerate(chunk):
            rank = i + idx + 1
            print(f"\n  +-- RANK #{rank} {'--' + '-' * 48}")
            print(format_investor(investor))
            
        if i + page_size < len(final_investors):
            try:
                next_end = min(i + page_size * 2, len(final_investors))
                input(f"\n  [Press Enter to view results {i + page_size + 1} to {next_end}]...")
            except (KeyboardInterrupt, EOFError):
                print("\n  [!] Display aborted by user. Saving results...")
                break

    # ── Phase 7: Save ────────────────────────────────────────────────────
    print(f"\n{'=' * 62}")
    print("  SAVING RESULTS")
    print(f"{'=' * 62}")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    geo_slug = geography.lower().replace(" ", "_") if geography else "global"
    output_file = f"investors_{category_slug}_{geo_slug}_{timestamp}.json"
    csv_file = f"investors_{category_slug}_{geo_slug}_{timestamp}.csv"

    # Enrich with guessed emails
    generate_guessed_emails(final_investors)

    # 1. Save timestamped TRANSACTION record for this run
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(final_investors, f, indent=2, ensure_ascii=False)
    export_to_csv(final_investors, csv_file)

    # 2. Load preset master database, merge new unique firms, and save back to investors_{category_slug}.json / investors_{category_slug}.csv
    master_investors = []
    if os.path.exists(master_json_file):
        try:
            with open(master_json_file, "r", encoding="utf-8") as f:
                master_investors = json.load(f)
                if not isinstance(master_investors, list):
                    master_investors = []
        except Exception:
            pass

    # Map existing domains in preset master list
    seen_master_domains = set()
    for inv in master_investors:
        web = inv.get("website", "")
        if web:
            domain = urlparse(web).netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            if domain:
                seen_master_domains.add(domain)

    merged_count = 0
    for inv in final_investors:
        web = inv.get("website", "")
        if web:
            domain = urlparse(web).netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            if domain and domain not in seen_master_domains:
                master_investors.append(inv)
                seen_master_domains.add(domain)
                merged_count += 1
        else:
            master_investors.append(inv)
            merged_count += 1

    # Overwrite preset master files
    with open(master_json_file, "w", encoding="utf-8") as f:
        json.dump(master_investors, f, indent=2, ensure_ascii=False)
        
    export_to_csv(master_investors, master_csv_file)

    # 3. Save/Upsert to PostgreSQL database if active
    if db_active:
        try:
            from app.database.operations import save_investors_to_db
            db_saved = save_investors_to_db(final_investors, category_slug)
            print(f"  [DATABASE] Successfully saved/upserted {db_saved} investors to database.")
        except Exception as e:
            print(f"  [DATABASE] Failed to save investors to database: {e}")

    print(f"  [+]  Saved {len(final_investors)} new investors to transactional logs")
    print(f"  [+]  Merged {merged_count} new unique investors into preset master files (Total: {len(master_investors)})")
    print(f"  [>]  {output_file}")
    print(f"  [>]  {csv_file}")
    print(f"  [>]  {master_csv_file} / {master_json_file} (updated preset master database)")

    # ── Summary ──────────────────────────────────────────────────────────
    print(f"\n{'=' * 62}")
    print("  PIPELINE SUMMARY")
    print(f"{'=' * 62}")

    success_rate = len(final_investors) / max(len(to_process), 1) * 100
    avg_score = (
        sum(inv.get("confidence_score", 0) for inv in final_investors)
        / len(final_investors)
        if final_investors else 0
    )

    rows = [
        ("Queries run",         len(queries)),
        ("Geography filter",    geography if geography else "Global (none set)"),
        ("Raw URLs found",      len(all_results)),
        ("Unique URLs",         len(deduplicated)),
        ("URLs processed",      len(to_process)),
        ("Unique firms found",  len(final_investors)),
        ("Success rate",        f"{success_rate:.1f}%"),
        ("Avg confidence",      f"{avg_score:.1f}/{MAX_CONFIDENCE}"),
        ("Parser",              _active_backend_label()),
        ("Output file",         output_file),
    ]

    for label, value in rows:
        print(f"  {label:<24}  {value}")

    print(f"\n{'=' * 62}")
    print("  PIPELINE COMPLETE")
    print(f"{'=' * 62}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  [!]  Interrupted by user\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n  [!]  Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)