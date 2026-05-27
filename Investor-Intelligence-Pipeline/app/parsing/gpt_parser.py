"""
LLM parser for investor data extraction.

Provider priority (automatic fallback):
  1. Groq (Llama 3.3 70B) — best quality, free tier, fast
  2. Ollama (local)        — always available, no rate limits, lower quality

Set PARSER_BACKEND in .env to force a specific provider:
  PARSER_BACKEND=groq    — use Groq only
  PARSER_BACKEND=ollama  — use Ollama only
  PARSER_BACKEND=auto    — try Groq first, fall back to Ollama (default)
"""

import json
import re
import os
from typing import Dict, Any

from app.config.settings import GROQ_API_KEY, OLLAMA_MODEL
from app.parsing.schema import InvestorSchema

# Which backend to use — read from env, default to "auto"
PARSER_BACKEND = os.getenv("PARSER_BACKEND", "auto").lower()

# Groq model — Llama 3.3 70B is their best free option
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


# ---------------------------------------------------------------------------
# JSON extraction helper
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> str:
    """Pull the first complete JSON object out of raw model output."""
    raw = raw.strip()
    for fence in ("```json", "```JSON", "```"):
        if raw.startswith(fence):
            raw = raw[len(fence):]
            break
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    start = raw.find("{")
    if start == -1:
        return raw

    depth = 0
    for i, ch in enumerate(raw[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return raw[start: i + 1]
    return raw[start:]


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

def _build_prompt(content: str) -> str:
    prompt_base = """You are an investor intelligence extraction engine.

Your ONLY output must be a single valid JSON object. No markdown, no explanation, no text before or after the JSON.

EXTRACTION RULES (CRITICAL):
1. ONLY extract information explicitly stated in the content
2. DO NOT guess, invent, or hallucinate any information
3. Use "" (empty string) or [] (empty array) if information is not found
4. Extract names and contact details EXACTLY as they appear

FIELD SPECIFICATIONS:

STRING FIELDS:
- "firm": The official VC firm name — e.g. "Sequoia Capital", "Andreessen Horowitz"
- "website": The firm's primary website URL ONLY (not LinkedIn/Twitter/Crunchbase) — e.g. "https://www.sequoiacap.com"
- "thesis": 1-3 sentences on their investment philosophy — e.g. "Invest in AI/ML startups with founders from top tech companies" or ""
- "check_size": Investment check size range — e.g. "$100K-$500K", "$1-5M", or ""
- "fund_number": Fund iteration — e.g. "Fund VI", "Fund 2024", or ""
- "fund_size": Total fund size — e.g. "$200M", "$1.2B", or ""
- "active_status": Current investment status — e.g. "actively deploying Fund IV", "fully committed", or ""
- "pitch_process": How to pitch to them — e.g. "warm intros only", "submit at pitch@firm.com", or ""

ARRAY FIELDS (strings only):
- "focus_sectors": Industry sectors they invest in — e.g. ["AI", "SaaS", "Healthcare"]
- "domain_specializations": Specific tech domains — e.g. ["Large Language Models", "Voice AI"]
- "investment_stage": Funding stages — e.g. ["Seed", "Series A", "Series B"]
- "geography": Geographic regions — e.g. ["US", "Europe", "Asia", "San Francisco"]

OBJECT ARRAYS (with strict format):

"partners": List of investment team members
  - MUST include each person's full name + their role/title
  - DO NOT include if names aren't explicitly listed
  - CORRECT: [{"name": "Jane Smith", "role": "General Partner"}, {"name": "John Doe", "role": "Partner"}]
  - WRONG: [{"name": "Unknown Partner"}] or [{"name": "Jane Smith"}]

"portfolio_companies": List of companies they've invested in
  - Use PLAIN STRINGS, not objects
  - CORRECT: ["Airbnb", "Stripe", "GitLab"]
  - WRONG: [{"name": "Airbnb"}, {"name": "Stripe", "status": "acquired"}]

"contact_links": Ways to reach the firm
  - MUST have both "type" and "value" fields
  - Types: "email", "phone", "linkedin", "contact_form", "twitter", "website"
  - ONLY extract contact info that exists in the content
  - DO NOT extract the main website URL as a contact link (that's "website" field)
  - EXAMPLES:
    * {"type": "email", "value": "partners@firm.com"}
    * {"type": "phone", "value": "+1-650-555-0123"}
    * {"type": "linkedin", "value": "linkedin.com/company/sequoia-capital"}
    * {"type": "contact_form", "value": "https://www.firm.com/contact"}
    * {"type": "twitter", "value": "twitter.com/firm_vc"}
  - WRONG: {"type": "contact", "value": "https://www.firm.com"} (too vague, wrong URL)
  - If NO contact info found, use empty array: []

OUTPUT THIS EXACT JSON STRUCTURE:
{
    "firm": "",
    "website": "",
    "thesis": "",
    "focus_sectors": [],
    "domain_specializations": [],
    "investment_stage": [],
    "check_size": "",
    "fund_number": "",
    "fund_size": "",
    "active_status": "",
    "pitch_process": "",
    "partners": [],
    "portfolio_companies": [],
    "geography": [],
    "contact_links": []
}

CONTENT TO EXTRACT FROM:
"""
    return prompt_base + content + "\n\nJSON:\n"


_EMPTY: Dict[str, Any] = {
    "firm": "", "website": "", "thesis": "",
    "focus_sectors": [], "domain_specializations": [],
    "investment_stage": [], "check_size": "",
    "fund_number": "", "fund_size": "", 
    "active_status": "", "pitch_process": "",
    "partners": [], "portfolio_companies": [],
    "geography": [], "contact_links": [],
}


# ---------------------------------------------------------------------------
# Groq backend
# ---------------------------------------------------------------------------

def _parse_with_groq(content: str, model_name: str = GROQ_MODEL) -> Dict[str, Any]:
    """Call Groq API. Fails fast on rate limits to trigger fallback."""
    from openai import OpenAI

    client = OpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
        max_retries=1, # Fails fast so we can drop to the 8B model
    )

    response = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": _build_prompt(content)}],
        temperature=0,
        max_tokens=2048,
        # Ask for JSON output mode if supported
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or ""
    cleaned = _extract_json(raw)
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# Ollama backend
# ---------------------------------------------------------------------------

def _parse_with_ollama(content: str) -> Dict[str, Any]:
    """Call local Ollama. Raises on failure."""
    import ollama

    response = ollama.chat(
        model=OLLAMA_MODEL,
        options={"temperature": 0, "num_predict": 2048},
        messages=[{"role": "user", "content": _build_prompt(content)}],
    )
    raw = response["message"]["content"]
    cleaned = _extract_json(raw)
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# Validation & quality assessment
# ---------------------------------------------------------------------------

def _calculate_data_quality(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate data completeness and quality metrics for extracted investor data.
    
    Returns dict with:
    - total_fields: Total number of extractable fields
    - populated_fields: Number of non-empty fields
    - completeness_percent: Percentage of fields populated (0-100)
    - has_firm: Whether firm name was extracted
    - has_contact: Whether any contact information was found
    """
    important_fields = [
        "firm", "website", "focus_sectors", "domain_specializations",
        "investment_stage", "partners", "portfolio_companies", "geography",
        "contact_links"
    ]
    
    populated = 0
    for field in important_fields:
        value = result.get(field)
        # A field is "populated" if it's non-empty
        is_populated = bool(value) and (
            (isinstance(value, (list, dict)) and len(value) > 0) or
            (isinstance(value, str) and len(value.strip()) > 0)
        )
        if is_populated:
            populated += 1
    
    completeness = int((populated / len(important_fields)) * 100)
    
    return {
        "total_fields": len(important_fields),
        "populated_fields": populated,
        "completeness_percent": completeness,
        "has_firm": bool(result.get("firm", "").strip()),
        "has_contact": bool(result.get("contact_links", [])),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_investor(markdown_content: str) -> Dict[str, Any]:
    """
    Parse VC firm web content into a structured InvestorSchema dict.

    Content limits are applied per-backend:
      Groq  (70B) → 6,000 chars — reduced to fit within free tier TPM limits
      Ollama (3B) → 5,000 chars  — small models lose quality beyond this

    Tries backends in order based on PARSER_BACKEND setting:
      auto  → Groq first, Ollama fallback
      groq  → Groq only
      ollama → Ollama only
    """
    backends: list[tuple[str, Any, int, str]] = []

    if PARSER_BACKEND == "groq":
        backends = [
            ("Groq 70B", _parse_with_groq, 6000, GROQ_MODEL),
            ("Groq 8B", _parse_with_groq, 6000, "llama-3.1-8b-instant")
        ]
    elif PARSER_BACKEND == "ollama":
        backends = [("Ollama", _parse_with_ollama, 5000, OLLAMA_MODEL)]
    else:  # auto
        if GROQ_API_KEY:
            backends.append(("Groq 70B", _parse_with_groq, 6000, GROQ_MODEL))
            backends.append(("Groq 8B", _parse_with_groq, 6000, "llama-3.1-8b-instant"))
        backends.append(("Ollama", _parse_with_ollama, 5000, OLLAMA_MODEL))

    last_error: Exception | None = None

    for name, fn, char_limit, model_arg in backends:
        try:
            content = markdown_content[:char_limit]
            if "Groq" in name:
                parsed = fn(content, model_name=model_arg)
            else:
                parsed = fn(content)
            validated = InvestorSchema.model_validate(parsed)
            result = validated.model_dump()
            result["_parser"] = name
            
            # Add data quality metrics
            data_quality = _calculate_data_quality(result)
            result["_data_quality"] = data_quality
            
            # Log quality info
            if data_quality['completeness_percent'] < 30:
                print(f"  [⚠️]  Low-quality extraction: only {data_quality['populated_fields']}/{data_quality['total_fields']} fields populated")
            
            return result

        except Exception as e:
            err_str = str(e)
            if "rate_limit" in err_str.lower() or "429" in err_str:
                print(f"  [!]  {name} rate limited — trying next backend")
            elif "connection" in err_str.lower() or "refused" in err_str.lower():
                print(f"  [!]  {name} unavailable — trying next backend")
            else:
                print(f"  [!]  {name} error ({type(e).__name__}): {err_str[:120]}")
            last_error = e
            continue

    print(f"  [!]  All backends failed. Last error: {last_error}")
    return {**_EMPTY}