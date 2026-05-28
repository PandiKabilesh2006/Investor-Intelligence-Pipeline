from dotenv import load_dotenv
import os
import json

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
FIRECRAWL_API_URL = os.getenv("FIRECRAWL_API_URL", "").rstrip("/")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

TEST_MODE = os.getenv("TEST_MODE", "true").lower() in {
    "1",
    "true",
    "yes",
}

TEST_QUERY_LIMIT = int(os.getenv("TEST_QUERY_LIMIT", "10"))
TEST_URL_LIMIT = int(os.getenv("TEST_URL_LIMIT", "5"))
MAX_TOTAL_URLS = int(os.getenv("MAX_TOTAL_URLS", "500"))
RECRAWL_AFTER_DAYS = int(os.getenv("RECRAWL_AFTER_DAYS", "30"))
FIRECRAWL_TIMEOUT_SECONDS = int(os.getenv("FIRECRAWL_TIMEOUT_SECONDS", "45"))
RETRY_FAILED_URLS_ENABLED = os.getenv("RETRY_FAILED_URLS_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
FAILED_URL_RETRY_LIMIT = int(os.getenv("FAILED_URL_RETRY_LIMIT", "10"))
FAILED_URL_MAX_RETRIES = int(os.getenv("FAILED_URL_MAX_RETRIES", "3"))
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

_cors_origins = os.getenv(
    "CORS_ORIGINS",
    ",".join(
        [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
            "http://localhost:3002",
            "http://127.0.0.1:3002",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
)

try:
    CORS_ORIGINS = json.loads(_cors_origins)
    if not isinstance(CORS_ORIGINS, list):
        CORS_ORIGINS = []
except json.JSONDecodeError:
    CORS_ORIGINS = [
        origin.strip()
        for origin in _cors_origins.split(",")
        if origin.strip()
    ]

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "1234"))
DB_NAME = os.getenv("DB_NAME", "investor_intelligence")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
