import json
import time
import re
import ollama

from groq import Groq
from openai import OpenAI

from app.config.settings import (
    GROQ_API_KEY,
    OPENAI_API_KEY,
    OPENAI_MODEL
)
from app.config.taxonomy import CORE_SECTORS, INVESTMENT_STAGES

from app.utils.groq_circuit import (
    is_recoverable_groq_error,
    record_groq_70b_rate_limit_failure,
    should_use_groq_70b,
)
from app.utils.normalization import (
    normalize_geography,
    normalize_sector,
    normalize_stage,
)


# =========================================
# LLM CLIENTS
# =========================================

openai_client = OpenAI(

    api_key=OPENAI_API_KEY
) if OPENAI_API_KEY else None

groq_client = Groq(

    api_key=GROQ_API_KEY,

    max_retries=0,

    timeout=30.0
)


# =========================================
# MODELS
# =========================================

OLLAMA_MODEL = "qwen2.5:3b"

GROQ_PRIMARY_MODEL = "llama-3.3-70b-versatile"

GROQ_FALLBACK_MODEL = "llama-3.1-8b-instant"


# =========================================
# MAX CONTENT LENGTH
# =========================================

MAX_CONTENT_LENGTH = 4000


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

    "firm": "",

    "website": "",

    "partners": [],

    "focus_sectors": [],

    "investment_stage": [],

    "portfolio_companies": [],

    "geography": [],

    "contact_links": []
}


INVESTOR_JSON_SCHEMA = {

    "name": "investor_intelligence_record",

    "strict": True,

    "schema": {

        "type": "object",

        "additionalProperties": False,

        "properties": {

            "firm": {
                "type": "string"
            },

            "website": {
                "type": "string"
            },

            "partners": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "name": {"type": "string"},
                        "role": {"type": "string"},
                        "title": {"type": "string"},
                        "linkedin_url": {"type": "string"},
                        "twitter_url": {"type": "string"},
                        "source_url": {"type": "string"},
                        "extraction_confidence": {"type": "number"}
                    },
                    "required": [
                        "name",
                        "role",
                        "title",
                        "linkedin_url",
                        "twitter_url",
                        "source_url",
                        "extraction_confidence"
                    ]
                }
            },

            "focus_sectors": {
                "type": "array",
                "items": {
                    "type": "string"
                }
            },

            "investment_stage": {
                "type": "array",
                "items": {
                    "type": "string"
                }
            },

            "portfolio_companies": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "company_name": {"type": "string"},
                        "sector": {"type": "string"}
                    },
                    "required": [
                        "company_name",
                        "sector"
                    ]
                }
            },

            "geography": {
                "type": "array",
                "items": {
                    "type": "string"
                }
            },

            "contact_links": {
                "type": "array",
                "items": {
                    "type": "string"
                }
            }
        },

        "required": [
            "firm",
            "website",
            "partners",
            "focus_sectors",
            "investment_stage",
            "portfolio_companies",
            "geography",
            "contact_links"
        ]
    }
}


def empty_partner():

    return {

        "name": "",

        "role": "",

        "title": "",

        "linkedin_url": "",

        "twitter_url": "",

        "source_url": "",

        "extraction_confidence": 0.0
    }


def empty_portfolio_company():

    return {

        "company_name": "",

        "sector": ""
    }


# =========================================
# PROMPT BUILDER
# =========================================

def build_prompt(markdown_content):

    markdown_content = re.sub(

        r"\n{3,}",

        "\n\n",

        markdown_content
    )

    sector_options = "\n".join(f"- {sector}" for sector in CORE_SECTORS)
    stage_options = "\n".join(f"- {stage}" for stage in INVESTMENT_STAGES)

    return f"""
You are a venture capital intelligence
extraction system.

Your task is to extract structured
investor information from ONE SINGLE
venture capital firm or investment entity.

Return ONLY valid JSON.

----------------------------------------
SCHEMA
----------------------------------------

{{
  "firm": "",
  "website": "",
  "partners": [
    {{
      "name": "",
      "role": "",
      "title": "",
      "linkedin_url": "",
      "twitter_url": "",
      "source_url": "",
      "extraction_confidence": 0.0
    }}
  ],
  "focus_sectors": [],
  "investment_stage": [],
  "portfolio_companies": [
    {{
      "company_name": "",
      "sector": ""
    }}
  ],
  "geography": [],
  "contact_links": []
}}

----------------------------------------
CRITICAL RULES
----------------------------------------

- Extract ONLY ONE investor firm
- NEVER return multiple firms
- NEVER return arrays for "firm"
- "firm" must ALWAYS be a string
- Return ONLY valid JSON
- Do NOT hallucinate
- Do NOT explain anything
- Prefer extraction from explicit evidence
- Infer conservatively from context
  when highly confident
- Never invent unsupported facts
- Prefer high-confidence retrieval
  over unnecessary empty outputs
- Avoid unnecessary empty arrays

----------------------------------------
FIRM EXTRACTION RULES
----------------------------------------

Extract ONLY the PRIMARY investment
organization represented in the page.

If the page is a blog post, article, essay, guide, podcast,
newsletter, or content page published on an investment firm's own
website, the "firm" must be the publishing investment organization,
not the article headline, page title, author name, content series,
or post slug.

If the page is a blog post, article, listicle, directory, or guide
published by a non-investor company, agency, media site, vendor,
consultant, software product, or service provider, do NOT use the
publisher as the investor firm. Return an empty firm unless the page
contains a clear profile for one specific investment firm.

Do not use long editorial titles as firm names. A valid firm name
should be the organization brand that operates the fund, investment
firm, accelerator, angel network, or venture studio.

If multiple firms appear:
- choose the main organization
- ignore partner firms
- ignore portfolio investors
- ignore ecosystem mentions
- ignore co-investors

Reject public-sector non-fund entities as investor firms.
Do NOT treat these as VC firms unless the page explicitly shows
that they operate as an actual investment fund:
- government portals
- ministries
- policy bodies
- economic development agencies
- investment promotion websites
- trade/investment facilitation organizations

Examples:
- Correct:
  "firm": "Accel"

- WRONG:
  "firm": [
      "Accel",
      "Bessemer"
  ]

----------------------------------------
FOCUS SECTOR TAXONOMY
----------------------------------------

Allowed values:

{sector_options}

Map similar concepts semantically, but keep B2B and SaaS separate.
If a firm clearly invests in B2B SaaS, return both "B2B" and "SaaS".

Examples:
- conversational AI → Voice AI
- speech AI → Voice AI
- enterprise software → B2B
- SaaS → SaaS
- B2B SaaS → B2B, SaaS
- generative AI → Artificial Intelligence
- AI infrastructure → Artificial Intelligence
- workflow automation → B2B

----------------------------------------
INVESTMENT STAGE TAXONOMY
----------------------------------------

Allowed values:

{stage_options}

Examples:
- early-stage → Seed
- growth equity → Growth Stage
- expansion stage → Growth Stage

Infer conservatively.

----------------------------------------
GEOGRAPHY TAXONOMY
----------------------------------------

Return specific country names when the page explicitly
states a country focus or office/investment market.

Return broader regions only when the page itself uses a
broader region, for example:
- Europe
- Southeast Asia
- Middle East
- Global

Use geography only for the firm's own office location,
investment mandate, or explicitly stated investment regions.
Do NOT infer geography from portfolio company locations alone.
Do NOT infer geography from the search query.
If the firm's geographic focus is unclear, return [].
Use Global only when the page explicitly says global,
worldwide, international, or multiple major regions.

----------------------------------------
PARTNER EXTRACTION RULES
----------------------------------------

Extract ONLY individuals explicitly
part of the investment firm's internal
investment team.

Return each partner as an object with:
- name
- role
- title
- linkedin_url
- twitter_url
- source_url
- extraction_confidence

Possible roles:
- Partner
- Managing Partner
- General Partner
- Venture Partner
- Principal
- Investment Director

Use "title" for the exact page title when present.
Use "role" for the normalized investment role.
Use "source_url" for the profile/team page URL or page URL
where the person was found.
Use extraction_confidence from 0.0 to 1.0:
- 0.95 when name, role/title, and source URL are explicit
- 0.80 when name and role/title are explicit
- 0.65 when only name and team-page context are explicit

Do NOT include:
- startup founders
- portfolio executives
- article authors
- external advisors
- companies
- organizations

If unclear:
return empty array.

----------------------------------------
PORTFOLIO COMPANY EXTRACTION
----------------------------------------

Extract ONLY startup/company names
belonging to the firm's portfolio.

Return each portfolio company as an object with:
- company_name
- sector

Do NOT extract:
- investors
- sectors
- people
- technologies
- article titles

----------------------------------------
CONTACT LINK EXTRACTION
----------------------------------------

Extract ALL valid communication,
profile, social, or contact endpoints
associated with the investment organization
or its internal investment team.

Possible examples include:
- public profile URLs
- social media profiles
- communication pages
- founder/contact pages
- email addresses
- team profile URLs
- application/contact forms

Extract exact URLs only.

Never invent missing links.

Do not restrict extraction to
specific platforms.

----------------------------------------
SEMANTIC ENRICHMENT RULES
----------------------------------------

When explicit labels are unavailable,
infer cautiously using semantic context.

Examples:
- AI infrastructure startup investor
  → Artificial Intelligence

- enterprise workflow software investor
  → B2B

- conversational voice platform investor
  → Voice AI

- global multi-region portfolio
  → Global

- early-stage startup investor
  → Seed

Only infer when strongly supported
by the content.

Never hallucinate unsupported categories.

----------------------------------------
WEBSITE CONTENT
----------------------------------------

{markdown_content[:MAX_CONTENT_LENGTH]}
"""


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

                cleaned.append(item)

                continue

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


def ensure_partner_list(value):

    partners = []

    for item in ensure_list(value):

        if isinstance(item, dict):

            partner = empty_partner()

            partner["name"] = str(
                item.get("name", "")
            ).strip()

            partner["role"] = str(
                item.get("role", "")
            ).strip()

            partner["title"] = str(
                item.get("title", item.get("role", ""))
            ).strip()

            partner["linkedin_url"] = str(
                item.get("linkedin_url", "")
            ).strip()

            partner["twitter_url"] = str(
                item.get("twitter_url", "")
            ).strip()

            partner["source_url"] = str(
                item.get(
                    "source_url",
                    item.get("linkedin_url", "")
                )
            ).strip()

            try:
                partner["extraction_confidence"] = float(
                    item.get("extraction_confidence", 0.0) or 0.0
                )
            except (TypeError, ValueError):
                partner["extraction_confidence"] = 0.0

        else:

            partner = empty_partner()

            partner["name"] = str(item).strip()

        if partner["name"]:

            partners.append(partner)

    return partners


def ensure_portfolio_company_list(value):

    companies = []

    for item in ensure_list(value):

        if isinstance(item, dict):

            company = empty_portfolio_company()

            company["company_name"] = str(
                item.get("company_name", "")
                or
                item.get("name", "")
            ).strip()

            company["sector"] = str(
                item.get("sector", "")
            ).strip()

        else:

            company = empty_portfolio_company()

            company["company_name"] = str(item).strip()

        if company["company_name"]:

            companies.append(company)

    return companies


# =========================================
# OUTPUT NORMALIZATION
# =========================================

def normalize_output(parsed):

    if not isinstance(parsed, dict):

        return EMPTY_RESPONSE.copy()


    parsed.setdefault("firm", "")

    parsed.setdefault("website", "")

    parsed.setdefault("partners", [])

    parsed.setdefault("focus_sectors", [])

    parsed.setdefault("investment_stage", [])

    parsed.setdefault("portfolio_companies", [])

    parsed.setdefault("geography", [])

    parsed.setdefault("contact_links", [])


    # =====================================
    # FIRM NORMALIZATION
    # =====================================

    raw_firm = parsed.get(

        "firm",

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

            parsed["firm"] = cleaned_firms[0]

        else:

            parsed["firm"] = ""


    else:

        parsed["firm"] = str(

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

        "geography",

        "contact_links"
    ]:

        parsed[field] = ensure_list(

            parsed.get(field, [])
        )

    parsed["partners"] = ensure_partner_list(

        parsed.get("partners", [])
    )

    parsed["portfolio_companies"] = ensure_portfolio_company_list(

        parsed.get("portfolio_companies", [])
    )


    # =====================================
    # REMOVE DUPLICATES
    # =====================================

    for field in [

        "focus_sectors",

        "investment_stage",

        "geography",

        "contact_links"
    ]:

        parsed[field] = list(

            dict.fromkeys(parsed[field])
        )

    partner_map = {}

    for partner in parsed["partners"]:

        partner_map.setdefault(

            partner["name"].lower(),

            partner
        )

    parsed["partners"] = list(

        partner_map.values()
    )

    company_map = {}

    for company in parsed["portfolio_companies"]:

        company_map.setdefault(

            company["company_name"].lower(),

            company
        )

    parsed["portfolio_companies"] = list(

        company_map.values()
    )


    return parsed


# =========================================
# HUMAN NAME FILTER
# =========================================

def filter_partner_names(partners):

    filtered = []
    blocked_terms = {
        "about",
        "accelerator",
        "blog",
        "capital",
        "companies",
        "contact",
        "events",
        "focus",
        "fund",
        "funding",
        "home",
        "investment",
        "investments",
        "investor",
        "investors",
        "news",
        "partners",
        "portfolio",
        "press",
        "privacy",
        "sectors",
        "stage",
        "startups",
        "team",
        "terms",
        "thesis",
        "ventures",
    }

    name_pattern = re.compile(

        r"^[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'.-]+"
        r"(?:\s+(?:[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'.-]+)){1,5}$"
    )


    for partner in partners:

        if isinstance(partner, dict):

            partner_record = partner.copy()

            partner_name = str(
                partner_record.get("name", "")
            ).strip()

        else:

            partner_record = empty_partner()

            partner_name = str(partner).strip()

            partner_record["name"] = partner_name


        if not name_pattern.match(partner_name):

            continue

        name_words = {
            word.strip("'.-").lower()
            for word in partner_name.split()
        }

        if name_words & blocked_terms:

            continue


        partner_record["name"] = partner_name

        filtered.append(partner_record)


    unique = {}

    for partner in filtered:

        unique.setdefault(

            partner["name"].lower(),

            partner
        )


    return list(

        unique.values()
    )


# =========================================
# CONTACT LINK FILTER
# =========================================

def filter_contact_links(links):

    filtered = []


    for link in links:

        if link is None:

            continue


        link = str(link).strip()


        if not link:

            continue


        # =====================================
        # VALID URL
        # =====================================

        if re.match(

            r"^https?://",

            link,

            re.IGNORECASE
        ):

            filtered.append(link)

            continue


        # =====================================
        # EMAIL
        # =====================================

        if re.match(

            r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$",

            link
        ):

            filtered.append(link)

            continue


        # =====================================
        # MAILTO
        # =====================================

        if link.lower().startswith(

            "mailto:"
        ):

            filtered.append(link)

            continue


    return list(

        dict.fromkeys(filtered)
    )


# =========================================
# TAXONOMY NORMALIZATION
# =========================================

def apply_taxonomy_normalization(parsed):

    parsed["focus_sectors"] = normalize_sector(
        parsed["focus_sectors"]
    )

    parsed["investment_stage"] = normalize_stage(
        parsed["investment_stage"]
    )

    parsed["geography"] = normalize_geography(
        parsed["geography"]
    )


    parsed["partners"] = filter_partner_names(

        parsed["partners"]
    )


    parsed["contact_links"] = filter_contact_links(

        parsed["contact_links"]
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

            if "enterprise software" in content_lower or "workflow automation" in content_lower:

                parsed["focus_sectors"].append(

                    "B2B"
                )

            if "saas" in content_lower:

                parsed["focus_sectors"].append(

                    "SaaS"
                )


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


# =========================================
# OPENAI PARSER
# =========================================

def parse_with_openai(prompt):

    if not openai_client:

        raise RuntimeError(

            "OPENAI_API_KEY is not configured"
        )


    response = openai_client.chat.completions.create(

        model=OPENAI_MODEL,

        temperature=0,

        response_format={

            "type": "json_schema",

            "json_schema": INVESTOR_JSON_SCHEMA
        },

        messages=[

            {
                "role": "system",

                "content": (
                    "You extract investor intelligence and return only "
                    "schema-valid JSON."
                )
            },

            {
                "role": "user",

                "content": prompt
            }
        ]
    )


    message = response.choices[0].message

    refusal = getattr(

        message,

        "refusal",

        None
    )

    if refusal:

        raise RuntimeError(

            f"OpenAI refused structured extraction: {refusal}"
        )


    output = message.content

    return extract_json(output)


# =========================================
# GROQ PARSER
# =========================================

def parse_with_groq(

    prompt,

    model_name
):

    response = groq_client.chat.completions.create(

        model=model_name,

        temperature=0,

        response_format={

            "type": "json_object"
        },

        messages=[

            {
                "role": "user",

                "content": prompt
            }
        ]
    )


    output = (

        response
        .choices[0]
        .message
        .content
    )


    return extract_json(output)


def _postprocess_parsed(parsed, markdown_content):

    parsed = normalize_output(parsed)

    parsed = apply_taxonomy_normalization(parsed)

    parsed = recover_sparse_fields(parsed, markdown_content)

    return parsed


def _parse_with_groq_8b_then_ollama(prompt, markdown_content):

    print("Switching to Groq 8B...")

    try:

        parsed = parse_with_groq(prompt, GROQ_FALLBACK_MODEL)

        parsed = _postprocess_parsed(parsed, markdown_content)

        print("Parsed using Groq 8B")

        time.sleep(8)

        return parsed

    except Exception as groq_8b_error:

        groq_8b_message = str(groq_8b_error).lower()

        print(f"Groq 8B failed: {groq_8b_error}")

        wait_time = extract_retry_wait(groq_8b_message)

        print(f"Waiting {wait_time}s before Ollama fallback...")

        time.sleep(wait_time)

        if not is_recoverable_groq_error(groq_8b_message):

            return EMPTY_RESPONSE

        print("Switching to Ollama...")

        try:

            parsed = parse_with_ollama(prompt)

            parsed = _postprocess_parsed(parsed, markdown_content)

            print("Parsed using Ollama")

            return parsed

        except Exception as ollama_error:

            print(f"Ollama failed: {ollama_error}")

            return EMPTY_RESPONSE


def _parse_with_groq_70b_then_8b_then_ollama(prompt, markdown_content):

    if should_use_groq_70b():

        try:

            parsed = parse_with_groq(prompt, GROQ_PRIMARY_MODEL)

            parsed = _postprocess_parsed(parsed, markdown_content)

            print("Parsed using Groq 70B")

            time.sleep(8)

            return parsed

        except Exception as groq_70b_error:

            error_message = str(groq_70b_error).lower()

            print(f"Groq 70B failed: {groq_70b_error}")

            if is_recoverable_groq_error(error_message):

                record_groq_70b_rate_limit_failure()

                wait_time = extract_retry_wait(error_message)

                print(f"Waiting {wait_time}s before Groq 8B fallback...")

                time.sleep(wait_time)

            else:

                print("Groq 70B error is not recoverable; trying Groq 8B.")

    else:

        print(
            "Groq 70B skipped (rate-limit circuit open); using 8B directly."
        )


    return _parse_with_groq_8b_then_ollama(prompt, markdown_content)


# =========================================
# MAIN PARSER
# =========================================

def parse_investor(markdown_content):

    prompt = build_prompt(markdown_content)

    try:

        parsed = parse_with_openai(prompt)

        parsed = _postprocess_parsed(parsed, markdown_content)

        print(f"Parsed using OpenAI {OPENAI_MODEL}")

        return parsed

    except Exception as openai_error:

        print(f"OpenAI failed: {openai_error}")

        print("Switching to Groq 70B...")

    return _parse_with_groq_70b_then_8b_then_ollama(

        prompt,

        markdown_content
    )
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
