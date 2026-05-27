import json
import time
import re
import ollama

from groq import Groq
from openai import OpenAI

from app.config.settings import (
    GROQ_API_KEY,
    OPENAI_API_KEY,
    PARSER_MAX_CONTENT_LENGTH,
    PARTNER_MIN_CONFIDENCE,
    PARTNER_ROLE_TITLES,
    GROQ_PRIMARY_MODEL,
    GROQ_FALLBACK_MODEL,
    OPENAI_PRIMARY_MODEL,
)
from app.validation.investor_validation import validate_parsed_investor
from app.prompts.loader import load_prompt


# =========================================
# CLIENTS
# =========================================

groq_client = Groq(
    api_key=GROQ_API_KEY,
    max_retries=0,
    timeout=30.0
)

openai_client = OpenAI(
    api_key=OPENAI_API_KEY
) if OPENAI_API_KEY else None

# Groq instant model for second fallback
GROQ_INSTANT_MODEL = "llama-3.1-8b-instant"


# =========================================
# MODELS
# =========================================

OLLAMA_MODEL = "qwen2.5:3b"

# Imported models configured from settings


# =========================================
# MAX CONTENT LENGTH
# =========================================
# Increased from 4000 to 8000 chars.
# Team/partner sections appear late in
# VC pages — truncating at 4000 often
# cuts them off before any names appear.
# Groq llama-3.3-70b supports 128k ctx,
# so 8000 chars is still very fast & cheap.

MAX_CONTENT_LENGTH = PARSER_MAX_CONTENT_LENGTH


# =========================================
# RECOVERABLE GROQ ERRORS
# =========================================

RECOVERABLE_GROQ_ERRORS = [

    "rate limit",

    "429",

    "too many requests",

    "rate_limit_exceeded",

    "tokens per minute",

    "requests per minute",

    "request too large",

    "model_decommissioned",

    "service unavailable",

    "overloaded",

    "internal server error"
]


# =========================================
# EMPTY FALLBACK
# =========================================

EMPTY_RESPONSE = {
    "firm_name": "",
    "website": "",
    "partners": [],
    "focus_sectors": [],
    "investment_stage": [],
    "portfolio_companies": [],
    "geography": []
}


# =========================================
# PROMPT BUILDER
# =========================================

def _smart_extract(markdown_content, max_chars=20000):
    """
    Extract the most partner-relevant slice of a markdown page.
    Strategy:
      - Always include the first 2000 chars (firm name, website, overview).
      - Find the earliest section header that signals team/people content.
      - Include up to (max_chars - 2000) chars starting from that section.
    This ensures partner names on large pages aren't cut off.
    """
    if len(markdown_content) <= max_chars:
        return markdown_content

    header = markdown_content[:2000]

    TEAM_SIGNALS = [
        r"(?m)^#{1,3}\s*(team|people|partners?|leadership|investment team|our team|the team|general partners?|managing partners?|board partners?)\s*$",
        r"General Partner",
        r"Managing Partner",
        r"linkedin\.com/in/",
    ]

    body_start = None
    for pattern in TEAM_SIGNALS:
        m = re.search(pattern, markdown_content, re.IGNORECASE)
        if m:
            if body_start is None or m.start() < body_start:
                body_start = m.start()

    if body_start is None:
        # Fallback: if no team section pattern matches, just return the first max_chars characters
        return markdown_content[:max_chars]

    body_budget = max_chars - len(header)
    body = markdown_content[body_start: body_start + body_budget]

    if body_start > 2000:
        # Avoid duplicating the header if team section is near the start
        return header + "\n\n...[content skipped]...\n\n" + body
    return header + body


def build_prompt(markdown_content):

    markdown_content = re.sub(

        r"\n{3,}",

        "\n\n",

        markdown_content
    )

    extracted = _smart_extract(markdown_content, max_chars=20000)

    template = load_prompt("parser_prompt.txt")
    return template.replace("{extracted}", extracted)


# =========================================
# SAFE LIST NORMALIZATION
# =========================================

def ensure_list(value):

    if value is None:

        return []


    if isinstance(value, list):

        cleaned = []

        for item in value:

            if item is None:

                continue

            if isinstance(item, dict):

                # Try to extract human name or company/firm name if returned as dict
                item = (

                    item.get("name") or 

                    item.get("company") or 

                    item.get("firm") or 

                    (list(item.values())[0] if item.values() else "")

                )

            item = str(item).strip()

            if item:

                cleaned.append(item)

        return cleaned


    if isinstance(value, str):

        value = value.strip()

        if not value:

            return []

        return [value]


    return []


# =========================================
# PARTNER RECORD NORMALIZATION
# =========================================

def normalize_partner_records(value):

    raw_partners = value if isinstance(value, list) else ensure_list(value)

    normalized = []

    for item in raw_partners:

        if item is None:

            continue

        if isinstance(item, dict):

            name = str(item.get("name", "")).strip()

            role = str(item.get("role", "")).strip()

            linkedin_url = str(item.get("linkedin_url", "")).strip()

            twitter_url = str(item.get("twitter_url", "")).strip()

        else:

            name = str(item).strip()

            role = ""

            linkedin_url = ""

            twitter_url = ""

        normalized.append({
            "name": name,
            "role": role,
            "linkedin_url": linkedin_url,
            "twitter_url": twitter_url,
            "confidence": float(item.get("confidence", 0.85)) if isinstance(item, dict) else 0.85,
        })

    return normalized


def normalize_portfolio_companies(value):
    raw_companies = value if isinstance(value, list) else ensure_list(value)
    normalized = []
    for item in raw_companies:
        if item is None:
            continue
        if isinstance(item, dict):
            company_name = str(item.get("company_name", "")).strip()
            sector = str(item.get("sector", "")).strip()
        else:
            company_name = str(item).strip()
            sector = ""
        if company_name:
            normalized.append({
                "company_name": company_name,
                "sector": sector
            })
    return normalized


# =========================================
# OUTPUT NORMALIZATION
# =========================================

def normalize_output(parsed):

    if not isinstance(parsed, dict):

        return EMPTY_RESPONSE.copy()


    parsed.setdefault("firm_name", "")

    parsed.setdefault("website", "")

    parsed.setdefault("partners", [])

    parsed.setdefault("focus_sectors", [])

    parsed.setdefault("investment_stage", [])

    parsed.setdefault("portfolio_companies", [])

    parsed.setdefault("geography", [])


    # =====================================
    # FIRM NORMALIZATION
    # =====================================

    raw_firm = parsed.get(

        "firm_name",

        ""
    )


    if isinstance(raw_firm, list):

        cleaned_firms = []


        for item in raw_firm:

            if item is None:

                continue

            item = str(item).strip()

            if item:

                cleaned_firms.append(item)


        if cleaned_firms:

            parsed["firm_name"] = cleaned_firms[0]

        else:

            parsed["firm_name"] = ""


    else:

        parsed["firm_name"] = str(

            raw_firm

        ).strip()


    # =====================================
    # WEBSITE NORMALIZATION
    # =====================================

    parsed["website"] = str(

        parsed.get(

            "website",

            ""
        )

    ).strip()


    # =====================================
    # SAFE ARRAY NORMALIZATION
    # =====================================

    for field in [

        "focus_sectors",

        "investment_stage",

        "geography"
    ]:

        parsed[field] = ensure_list(

            parsed.get(field, [])
        )

    parsed["partners"] = normalize_partner_records(

        parsed.get("partners", [])
    )

    parsed["portfolio_companies"] = normalize_portfolio_companies(

        parsed.get("portfolio_companies", [])
    )


    # =====================================
    # REMOVE DUPLICATES
    # =====================================

    for field in [

        "focus_sectors",

        "investment_stage",

        "geography"
    ]:

        parsed[field] = list(

            dict.fromkeys(parsed[field])
        )

    deduped_partners = {}

    for partner in parsed["partners"]:

        key = partner.get("name", "").strip().lower()

        if key and key not in deduped_partners:

            deduped_partners[key] = partner

    parsed["partners"] = list(deduped_partners.values())


    deduped_companies = {}

    for company in parsed["portfolio_companies"]:

        key = company.get("company_name", "").strip().lower()

        if key and key not in deduped_companies:

            deduped_companies[key] = company

    parsed["portfolio_companies"] = list(deduped_companies.values())


    return parsed


def finalize_parsed_record(parsed: dict, source_url: str = "") -> dict:
    if source_url:
        parsed["source_url"] = source_url

    is_valid, reason, cleaned = validate_parsed_investor(parsed)

    if not is_valid:
        print(f"Parser output rejected ({reason}): {cleaned.get('firm_name', '')!r}")
        return EMPTY_RESPONSE.copy()

    return cleaned


# =========================================
# HUMAN NAME FILTER
# =========================================

def filter_partner_names(partners):

    filtered = []

    role_titles = {
        title.strip().lower()
        for title in PARTNER_ROLE_TITLES
    }


    for partner in partners:

        if isinstance(partner, dict):

            partner_record = partner.copy()

            partner_name = str(partner_record.get("name", "")).strip()

        else:

            partner_name = str(partner).strip()

            partner_record = {

                "name": partner_name,

                "role": "",

                "linkedin_url": "",

                "twitter_url": ""
            }

        if re.match(r"^Partner\s+\d+$", partner_name, re.IGNORECASE):

            continue


        if partner_name.lower() in role_titles:

            continue


        if not re.match(r"^[a-zA-Z0-9'\-\.\s]+$", partner_name) or not re.search(r"[a-zA-Z]", partner_name) or len(partner_name) < 3:
            continue

        partner_record["name"] = partner_name

        filtered.append(partner_record)


    deduped = {}

    for partner in filtered:

        key = partner["name"].lower()

        if key not in deduped:

            deduped[key] = partner

    return list(

        deduped.values()
    )


# =========================================
# TAXONOMY NORMALIZATION
# =========================================

def apply_taxonomy_normalization(parsed):

    sector_mapping = {
        "saas": "SaaS",
        "enterprise software": "SaaS",
        "b2b software": "B2B",
        "b2b software and services": "B2B",
        "voice agents": "Voice AI",
        "speech ai": "Voice AI",
        "conversational ai": "Voice AI",
        "generative ai": "Artificial Intelligence",
        "machine learning": "Artificial Intelligence",
        "ai infrastructure": "Artificial Intelligence",
        "workflow automation": "SaaS",
        "b2b": "B2B",
        "ai": "Artificial Intelligence",
        "b2b saas": "SaaS"
    }


    normalized_sectors = []


    for sector in parsed["focus_sectors"]:

        sector_lower = sector.lower().strip()


        if sector_lower in sector_mapping:

            normalized_sectors.append(

                sector_mapping[sector_lower]
            )

        else:

            normalized_sectors.append(

                sector
            )


    parsed["focus_sectors"] = list(

        dict.fromkeys(normalized_sectors)
    )


    stage_mapping = {

        "pre seed": "Pre-Seed",

        "early-stage": "Seed",

        "early stage": "Seed",

        "seed": "Seed",

        "series a": "Series A",

        "series b": "Series B",

        "growth equity": "Growth Stage",

        "growth": "Growth Stage",

        "buyouts": "Growth Stage",

        "expansion stage": "Growth Stage"
    }


    normalized_stages = []


    for stage in parsed["investment_stage"]:

        stage_lower = stage.lower().strip()


        if stage_lower in stage_mapping:

            normalized_stages.append(

                stage_mapping[stage_lower]
            )

        else:

            normalized_stages.append(

                stage
            )


    parsed["investment_stage"] = list(

        dict.fromkeys(normalized_stages)
    )


    geography_mapping = {
        "usa": "United States",
        "us": "United States",
        "united states of america": "United States",
        "uk": "United Kingdom",
        "united kingdom": "United Kingdom",
        "great britain": "United Kingdom",
        "england": "United Kingdom",
        "middle east and north africa": "Middle East",
        "mena": "Middle East",
        "sea": "Southeast Asia"
    }


    normalized_geography = []


    for geo in parsed["geography"]:

        geo_lower = geo.lower().strip()


        if geo_lower in geography_mapping:

            normalized_geography.append(

                geography_mapping[geo_lower]
            )

        else:

            normalized_geography.append(

                geo
            )


    parsed["geography"] = list(

        dict.fromkeys(normalized_geography)
    )


    parsed["partners"] = filter_partner_names(

        parsed["partners"]
    )


    return parsed


# =========================================
# EMPTY FIELD RECOVERY
# =========================================

def recover_sparse_fields(

    parsed,

    markdown_content
):

    content_lower = markdown_content.lower()


    # =====================================
    # SECTOR RECOVERY
    # =====================================

    if not parsed["focus_sectors"]:

        if (

            "artificial intelligence" in content_lower

            or

            "machine learning" in content_lower

            or

            "generative ai" in content_lower

            or

            "ai startup" in content_lower
        ):

            parsed["focus_sectors"].append(

                "Artificial Intelligence"
            )


        if (
            "saas" in content_lower
            or
            "enterprise software" in content_lower
            or
            "workflow automation" in content_lower
        ):
            parsed["focus_sectors"].extend([
                "B2B",
                "SaaS"
            ])


    # =====================================
    # STAGE RECOVERY
    # =====================================

    if not parsed["investment_stage"]:

        if (

            "early-stage" in content_lower

            or

            "early stage" in content_lower

            or

            "seed-stage" in content_lower

            or

            "seed investor" in content_lower
        ):

            parsed["investment_stage"].append(

                "Seed"
            )


        if "series a" in content_lower:

            parsed["investment_stage"].append(

                "Series A"
            )


    # =====================================
    # GEOGRAPHY RECOVERY
    # =====================================

    if not parsed["geography"]:

        if "india" in content_lower:

            parsed["geography"].append(

                "India"
            )


        if (

            "united states" in content_lower

            or

            "usa" in content_lower
        ):

            parsed["geography"].append(

                "United States"
            )


        if "europe" in content_lower:

            parsed["geography"].append(

                "Europe"
            )


    return parsed


# =========================================
# JSON EXTRACTION
# =========================================

def extract_json(text):

    cleaned = (

        text
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )


    start = cleaned.find("{")

    end = cleaned.rfind("}")


    if start == -1 or end == -1:

        raise ValueError(

            "No JSON object found"
        )


    json_text = cleaned[start:end + 1]


    return json.loads(json_text)


# =========================================
# RETRY WAIT EXTRACTION
# =========================================

def extract_retry_wait(error_message):

    match = re.search(

        r"try again in ([0-9.]+)s",

        error_message.lower()
    )

    if match:

        return float(match.group(1)) + 2

    return 15


# =========================================
# OLLAMA PARSER
# =========================================

def parse_with_ollama(prompt):

    response = ollama.chat(

        model=OLLAMA_MODEL,

        messages=[

            {
                "role": "user",

                "content": prompt
            }
        ],

        options={

            "temperature": 0
        }
    )


    output = (

        response["message"]["content"]
    )


    return extract_json(output)


def parse_with_openai(prompt):
    """Parse using OpenAI GPT-4o (primary LLM)."""
    response = openai_client.chat.completions.create(
        model=OPENAI_PRIMARY_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You are a venture capital intelligence extraction system. Return only valid JSON."},
            {"role": "user", "content": prompt}
        ]
    )
    output = response.choices[0].message.content
    return extract_json(output)


def parse_with_groq(prompt, model_name):
    response = groq_client.chat.completions.create(
        model=model_name,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}]
    )
    output = response.choices[0].message.content
    return extract_json(output)


# =========================================
# MAIN PARSER  — chain: OpenAI → Groq 70B → Groq Instant → Ollama
# =========================================

def parse_investor(markdown_content, source_url: str = "", firm_name: str = ""):

    prompt = build_prompt(markdown_content)

    def _finalize(parsed):
        if firm_name and parsed and not parsed.get("firm_name"):
            parsed["firm_name"] = firm_name
        parsed = normalize_output(parsed)
        parsed = apply_taxonomy_normalization(parsed)
        parsed = recover_sparse_fields(parsed, markdown_content)
        parsed = finalize_parsed_record(parsed, source_url=source_url)
        return parsed

    # ─── PRIMARY: OpenAI GPT-4o ───────────────────────────────────────────────
    if openai_client:
        try:
            parsed = parse_with_openai(prompt)
            parsed = _finalize(parsed)
            print(f"Parsed using OpenAI {OPENAI_PRIMARY_MODEL}")
            time.sleep(0.05)
            return parsed
        except Exception as openai_err:
            print(f"OpenAI {OPENAI_PRIMARY_MODEL} failed: {openai_err}")
            # fall through to Groq

    # ─── FALLBACK 1: Groq 70B ────────────────────────────────────────────────
    try:
        parsed = parse_with_groq(prompt, GROQ_PRIMARY_MODEL)
        parsed = _finalize(parsed)
        print(f"Parsed using Groq {GROQ_PRIMARY_MODEL}")
        time.sleep(3)
        return parsed
    except Exception as groq_70b_err:
        err_msg = str(groq_70b_err).lower()
        wait = extract_retry_wait(err_msg)
        print(f"Groq {GROQ_PRIMARY_MODEL} failed: {groq_70b_err} — waiting {wait}s")
        time.sleep(wait)

    # ─── FALLBACK 2: Groq Instant ────────────────────────────────────────────
    try:
        parsed = parse_with_groq(prompt, GROQ_INSTANT_MODEL)
        parsed = _finalize(parsed)
        print(f"Parsed using Groq instant ({GROQ_INSTANT_MODEL})")
        time.sleep(3)
        return parsed
    except Exception as groq_instant_err:
        err_msg = str(groq_instant_err).lower()
        wait = extract_retry_wait(err_msg)
        print(f"Groq instant {GROQ_INSTANT_MODEL} failed: {groq_instant_err} — waiting {wait}s")
        time.sleep(wait)

    # ─── FALLBACK 3: Ollama ──────────────────────────────────────────────────
    try:
        parsed = parse_with_ollama(prompt)
        parsed = _finalize(parsed)
        print("Parsed using Ollama")
        return parsed
    except Exception as ollama_err:
        print(f"Ollama failed: {ollama_err}")

    return EMPTY_RESPONSE.copy()
# import json
# import time
# import ollama


# # =========================================
# # OLLAMA MODEL
# # =========================================

# MODEL_NAME = "qwen2.5:7b"


# # =========================================
# # INVESTOR PARSER
# # =========================================

# def parse_investor(markdown_content):

#     prompt = f"""
# You are a venture capital intelligence
# extraction system.

# Your task is to extract structured investor
# information from a VC firm's website.

# Extract ONLY information explicitly mentioned
# in the content.

# Return ONLY valid JSON.

# Use this EXACT schema:

# {{
#   "firm": "",
#   "website": "",
#   "focus_sectors": [],
#   "investment_stage": [],
#   "partners": []
# }}

# IMPORTANT RULES:

# - Extract ONLY venture capital,
#   investment firm, or investor information

# - Do NOT extract startup founders

# - Do NOT extract article authors

# - Do NOT hallucinate

# - Do NOT explain anything

# - Return ONLY JSON

# - If information is missing,
#   return empty arrays

# - A VC firm can belong to MULTIPLE sectors

# - Extract ALL relevant sectors

# ----------------------------------------
# FOCUS SECTOR TAXONOMY
# ----------------------------------------

# Allowed focus_sectors:

# - Artificial Intelligence
# - Enterprise AI
# - B2B SaaS
# - Voice AI
# - Fintech
# - Healthcare
# - Developer Tools
# - AI Infrastructure

# ----------------------------------------
# SECTOR MAPPING RULES
# ----------------------------------------

# Voice AI:
# - voice agents
# - conversational AI
# - speech AI
# - call center AI

# → Voice AI

# Enterprise AI:
# - workflow automation
# - enterprise software
# - enterprise copilots

# → Enterprise AI

# B2B SaaS:
# - SaaS
# - cloud software
# - recurring software

# → B2B SaaS

# AI Infrastructure:
# - LLM infrastructure
# - vector databases
# - inference systems

# → AI Infrastructure

# Developer Tools:
# - API platforms
# - developer infrastructure
# - coding tools

# → Developer Tools

# ----------------------------------------
# INVESTMENT STAGE TAXONOMY
# ----------------------------------------

# Allowed investment_stage values:

# - Pre-Seed
# - Seed
# - Series A
# - Series B
# - Series C
# - Growth Stage
# - IPO Stage

# Normalize stages into ONLY these values.

# ----------------------------------------
# PARTNER EXTRACTION
# ----------------------------------------

# partners should contain:
# - VC partners
# - managing partners
# - investment team members
# - general partners

# Do NOT include:
# - startup founders
# - portfolio founders
# - article authors

# ----------------------------------------
# WEBSITE CONTENT
# ----------------------------------------

# {markdown_content[:12000]}
# """


#     # =========================================
#     # RETRY LOGIC
#     # =========================================

#     for attempt in range(3):

#         try:

#             response = ollama.chat(

#                 model=MODEL_NAME,

#                 messages=[

#                     {
#                         "role": "user",
#                         "content": prompt
#                     }
#                 ],

#                 options={

#                     "temperature": 0
#                 }
#             )


#             output = (

#                 response["message"]["content"]
#             )


#             cleaned = (

#                 output
#                 .replace("```json", "")
#                 .replace("```", "")
#                 .strip()
#             )


#             return json.loads(cleaned)


#         except Exception as error:

#             print(

#                 f"Ollama parsing failed: "
#                 f"{error}"
#             )

#             time.sleep(2)


#     # =========================================
#     # FALLBACK
#     # =========================================

#     return {

#         "firm": "",
#         "website": "",
#         "focus_sectors": [],
#         "investment_stage": [],
#         "partners": []
#     }
