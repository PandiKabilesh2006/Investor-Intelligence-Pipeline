from dotenv import load_dotenv
import os

load_dotenv()

OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY")
TAVILY_API_KEY    = os.getenv("TAVILY_API_KEY")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY      = os.getenv("GROQ_API_KEY")

# ---------------------------------------------------------------------------
# LLM Parser settings
# ---------------------------------------------------------------------------

# Which backend to use for investor parsing:
#   auto   → try Groq first, fall back to Ollama (recommended)
#   groq   → Groq only (best quality, free tier, ~1000 req/day)
#   ollama → Ollama only (local, unlimited, lower quality)
PARSER_BACKEND = os.getenv("PARSER_BACKEND", "auto")

# Groq model — Llama 3.3 70B is the best free option on Groq
# Other options: llama-3.1-8b-instant (faster, lower quality)
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Ollama model — used when Groq is unavailable or PARSER_BACKEND=ollama
# Better options (need ollama pull first):
#   qwen2.5:7b    (~4.7 GB, much better than 3b)
#   llama3.1:8b   (~4.7 GB)
#   mistral:7b    (~4.1 GB)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
DATABASE_URL = os.getenv("DATABASE_URL")