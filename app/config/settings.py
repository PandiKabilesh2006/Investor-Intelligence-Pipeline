from dotenv import load_dotenv
import os

load_dotenv()

def get_bool(name, default=False):
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on"
    }


def get_int(name, default):
    value = os.getenv(name)

    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


def get_float(name, default):
    value = os.getenv(name)

    if value is None:
        return default

    try:
        return float(value)
    except ValueError:
        return default


def get_csv(name, default):
    value = os.getenv(name)

    if value is None:
        return default

    cleaned = []

    for item in value.split(","):
        item = item.strip()

        if not item:
            continue

        if item == "<root>":
            item = ""

        cleaned.append(item)

    return cleaned or default


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GROQ_PRIMARY_MODEL = os.getenv("GROQ_PRIMARY_MODEL", "llama-3.3-70b-versatile")
GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "investor_intelligence")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

INGESTION_TEST_MODE = get_bool("INGESTION_TEST_MODE", False)
INGESTION_TEST_QUERY_LIMIT = get_int("INGESTION_TEST_QUERY_LIMIT", 40)
INGESTION_SEARCH_MAX_PAGES = get_int("INGESTION_SEARCH_MAX_PAGES", 10)
INGESTION_MAX_URLS_PER_RUN = get_int("INGESTION_MAX_URLS_PER_RUN", 500)
INGESTION_QUEUE_STATUS_LIMIT = get_int("INGESTION_QUEUE_STATUS_LIMIT", 500)
INGESTION_RECRAWL_AFTER_DAYS = get_int("INGESTION_RECRAWL_AFTER_DAYS", 30)
INGESTION_QUERY_DELAY_SECONDS = get_int("INGESTION_QUERY_DELAY_SECONDS", 2)

EXTRACTION_MAX_CONCURRENT = get_int("EXTRACTION_MAX_CONCURRENT", 5)
PARSER_MAX_CONTENT_LENGTH = get_int("PARSER_MAX_CONTENT_LENGTH", 8000)
PARTNER_MIN_CONFIDENCE = get_float("PARTNER_MIN_CONFIDENCE", 0.7)
TEAM_PAGE_PRIORITY = get_float("TEAM_PAGE_PRIORITY", 3.5)

TEAM_PAGE_PATHS = get_csv(
    "TEAM_PAGE_PATHS",
    [
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
        "/who-we-are"
    ]
)

EXTRACTION_SUBPAGES = get_csv(
    "EXTRACTION_SUBPAGES",
    [
        "",
        "/team",
        "/people",
        "/partners",
        "/about",
        "/leadership",
        "/portfolio",
        "/companies",
        "/contact"
    ]
)

REJECTED_DISCOVERY_DOMAINS = get_csv(
    "REJECTED_DISCOVERY_DOMAINS",
    [
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
        "seedtable.com",
        "tracxn.com"
    ]
)

PARTNER_ROLE_TITLES = get_csv(
    "PARTNER_ROLE_TITLES",
    [
        "partner",
        "managing partner",
        "general partner",
        "venture partner",
        "principal",
        "investment director",
        "founding partner",
        "senior partner",
        "limited partner",
        "advisor",
        "associate",
        "analyst",
        "team"
    ]
)

