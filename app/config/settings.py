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
FIRECRAWL_API_URL = os.getenv("FIRECRAWL_API_URL", "http://localhost:3002")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

OPENAI_PRIMARY_MODEL = os.getenv("OPENAI_PRIMARY_MODEL", "gpt-4o")

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
INGESTION_TOTAL_URL_BUDGET = get_int("INGESTION_TOTAL_URL_BUDGET", 0)
INGESTION_QUEUE_STATUS_LIMIT = get_int("INGESTION_QUEUE_STATUS_LIMIT", 500)
INGESTION_RECRAWL_AFTER_DAYS = get_int("INGESTION_RECRAWL_AFTER_DAYS", 30)
INGESTION_QUERY_DELAY_SECONDS = get_int("INGESTION_QUERY_DELAY_SECONDS", 2)
INGESTION_ALLOW_MOCK_DATA = get_bool("INGESTION_ALLOW_MOCK_DATA", False)
INGESTION_REQUIRE_RAW_PROVENANCE = get_bool("INGESTION_REQUIRE_RAW_PROVENANCE", True)
INGESTION_MIN_MARKDOWN_LENGTH = get_int("INGESTION_MIN_MARKDOWN_LENGTH", 500)
RAW_DATA_FOLDER = os.getenv("RAW_DATA_FOLDER", "raw_markdown")
PARSED_DATA_FOLDER = os.getenv("PARSED_DATA_FOLDER", "parsed_json")

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
        "tracxn.com",
        "github.com",
        "gitlab.com",
        "bitbucket.org",
        "reddit.com",
        "news.ycombinator.com",
        "producthunt.com",
        "glassdoor.com",
        "indeed.com",
        "google.com",
        "apple.com",
        "amazon.com",
        "microsoft.com",
        "notion.site",
        "wordpress.com",
        "blogspot.com",
        "tumblr.com",
        "quora.com",
        "stackoverflow.com",
        "dev.to",
        "hackernoon.com",
        "businessinsider.com",
        "cnbc.com",
        "ft.com",
        "wsj.com",
        "nytimes.com",
        "theverge.com",
        "wired.com",
        "economist.com",
        "inc.com",
        "entrepreneur.com",
        "fool.com",
        "seekingalpha.com",
        "prnewswire.com",
        "businesswire.com",
    ]
)

REJECTED_FIRM_NAME_EXACT = get_csv(
    "REJECTED_FIRM_NAME_EXACT",
    [
        "GitHub",
        "Forbes",
        "TechCrunch",
        "Bloomberg",
        "Reuters",
        "LinkedIn",
        "Crunchbase",
        "Wikipedia",
        "Medium",
        "Substack",
        "Twitter",
        "X",
        "YouTube",
        "Facebook",
        "Instagram",
        "AngelList",
        "Wellfound",
        "Product Hunt",
        "Hacker News",
        "Y Combinator News",
        "Stack Overflow",
        "Google",
        "Apple",
        "Microsoft",
        "Amazon",
        "Unknown",
        "N/A",
        "Home",
        "About",
        "Team",
        "Portfolio",
        "Contact",
        "Blog",
        "News",
        "Press",
    ],
)

REJECTED_FIRM_NAME_SUBSTRINGS = get_csv(
    "REJECTED_FIRM_NAME_SUBSTRINGS",
    [
        "github",
        "forbes",
        "techcrunch",
        "bloomberg",
        "reuters",
        "wikipedia",
        "linkedin",
        "crunchbase",
        "medium.com",
        "substack",
        "youtube",
        "twitter",
        "facebook",
        "instagram",
        "newsletter",
        "subscribe",
        "all rights reserved",
        "privacy policy",
        "terms of service",
        "cookie policy",
        "read more",
        "click here",
        "venture capital firms",
        "top investors",
        "best investors",
        "investor list",
    ],
)

REJECTED_URL_PATH_PATTERNS = get_csv(
    "REJECTED_URL_PATH_PATTERNS",
    [
        r"/tag/",
        r"/tags/",
        r"/category/",
        r"/author/",
        r"/wp-content/",
        r"/feed",
        r"/rss",
        r"/login",
        r"/signup",
        r"/register",
        r"/cart",
        r"/checkout",
        r"/jobs/",
        r"/careers/",
        r"/press-release",
        r"/article/",
        r"/articles/",
        r"/news/",
        r"/blog/",
        r"/stories/",
    ],
)

RELEVANCE_MIN_CONFIDENCE = get_float("RELEVANCE_MIN_CONFIDENCE", 0.75)

ALLOWED_INVESTOR_SOURCE_TYPES = get_csv(
    "ALLOWED_INVESTOR_SOURCE_TYPES",
    [
        "investor_profile",
        "investor_directory",
        "investor_mention",
    ],
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
