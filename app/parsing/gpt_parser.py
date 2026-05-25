import json
import time
import re
import ollama

from groq import Groq

from app.config.settings import (
    GROQ_API_KEY,
    PARSER_MAX_CONTENT_LENGTH,
    PARTNER_MIN_CONFIDENCE,
    PARTNER_ROLE_TITLES,
    GROQ_PRIMARY_MODEL,
    GROQ_FALLBACK_MODEL
)


# =========================================
# GROQ CLIENT
# =========================================

groq_client = Groq(

    api_key=GROQ_API_KEY,

    max_retries=0,

    timeout=30.0
)


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

    "firm": "",

    "website": "",

    "partners": [],

    "focus_sectors": [],

    "investment_stage": [],

    "portfolio_companies": [],

    "geography": [],

    "contact_links": []
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
    {
      "name": "",
      "role": "",
      "linkedin_url": "",
      "twitter_url": "",
      "source_url": "",
      "confidence": 0.0
    }
  ],
  "focus_sectors": [],
  "investment_stage": [],
  "portfolio_companies": [],
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

If multiple firms appear:
- choose the main organization
- ignore partner firms
- ignore portfolio investors
- ignore ecosystem mentions
- ignore co-investors

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

- Artificial Intelligence
- Enterprise AI
- B2B SaaS
- Voice AI

Map similar concepts semantically.

Examples:
- conversational AI → Voice AI
- speech AI → Voice AI
- enterprise software → B2B SaaS
- SaaS → B2B SaaS
- generative AI → Artificial Intelligence
- AI infrastructure → Artificial Intelligence
- workflow automation → B2B SaaS

----------------------------------------
INVESTMENT STAGE TAXONOMY
----------------------------------------

Allowed values:

- Pre-Seed
- Seed
- Series A
- Series B
- Growth Stage

Examples:
- early-stage → Seed
- growth equity → Growth Stage
- expansion stage → Growth Stage

Infer conservatively.

----------------------------------------
GEOGRAPHY TAXONOMY
----------------------------------------

Allowed values:

- India
- United States
- Europe
- Southeast Asia
- Middle East
- Global

----------------------------------------
PARTNER EXTRACTION RULES
----------------------------------------

Extract ONLY individuals explicitly
part of the investment firm's internal
investment team.

Possible roles:
- Partner
- Managing Partner
- General Partner
- Venture Partner
- Principal
- Investment Director

Do NOT include:
- startup founders
- portfolio executives
- article authors
- external advisors
- companies
- organizations

If unclear:
return empty array.

For each partner, return an object with:
- name: full human name
- role: explicit role/title if visible
- linkedin_url: exact LinkedIn URL if visible
- twitter_url: exact X/Twitter URL if visible
- source_url: exact source page URL if visible in content
- confidence: number from 0.0 to 1.0

Do not return placeholders like
"Partner 1", "Partner 2", or role-only names.

----------------------------------------
PORTFOLIO COMPANY EXTRACTION
----------------------------------------

Extract ONLY startup/company names
belonging to the firm's portfolio.

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
  → B2B SaaS

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

            source_url = str(item.get("source_url", "")).strip()

            confidence = item.get("confidence", 0.0)

        else:

            name = str(item).strip()

            role = ""

            linkedin_url = ""

            twitter_url = ""

            source_url = ""

            confidence = 0.7

        try:

            confidence = float(confidence)

        except (TypeError, ValueError):

            confidence = 0.0

        normalized.append({

            "name": name,

            "role": role,

            "linkedin_url": linkedin_url,

            "twitter_url": twitter_url,

            "source_url": source_url,

            "confidence": confidence
        })

    return normalized


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

        "portfolio_companies",

        "geography",

        "contact_links"
    ]:

        parsed[field] = ensure_list(

            parsed.get(field, [])
        )

    parsed["partners"] = normalize_partner_records(

        parsed.get("partners", [])
    )


    # =====================================
    # REMOVE DUPLICATES
    # =====================================

    for field in [

        "focus_sectors",

        "investment_stage",

        "portfolio_companies",

        "geography",

        "contact_links"
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


    return parsed


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

                "twitter_url": "",

                "source_url": "",

                "confidence": 0.7
            }

        if re.match(r"^Partner\s+\d+$", partner_name, re.IGNORECASE):

            continue


        if partner_name.lower() in role_titles:

            continue


        if not re.match(

            r"^[A-Z][a-zA-Z'\-]+(?:\s[A-Z][a-zA-Z'\-]+)+$",

            partner_name
        ):

            continue

        try:

            confidence = float(partner_record.get("confidence", 0.0))

        except (TypeError, ValueError):

            confidence = 0.0

        if confidence < PARTNER_MIN_CONFIDENCE:

            continue


        partner_record["name"] = partner_name

        partner_record["confidence"] = confidence

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

    sector_mapping = {

        "saas": "B2B SaaS",

        "enterprise software": "B2B SaaS",

        "b2b software": "B2B SaaS",

        "b2b software and services": "B2B SaaS",

        "voice agents": "Voice AI",

        "speech ai": "Voice AI",

        "conversational ai": "Voice AI",

        "generative ai": "Artificial Intelligence",

        "machine learning": "Artificial Intelligence",

        "ai infrastructure": "Artificial Intelligence",

        "workflow automation": "B2B SaaS"
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

        "uk": "Europe",

        "middle east and north africa": "Middle East"
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

            parsed["focus_sectors"].append(

                "B2B SaaS"
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


# =========================================
# MAIN PARSER
# =========================================

def parse_investor(markdown_content):

    prompt = build_prompt(

        markdown_content
    )


    # =====================================
    # PRIMARY: GROQ 70B
    # =====================================

    try:

        parsed = parse_with_groq(

            prompt,

            GROQ_PRIMARY_MODEL
        )

        parsed = normalize_output(

            parsed
        )

        parsed = apply_taxonomy_normalization(

            parsed
        )

        parsed = recover_sparse_fields(

            parsed,

            markdown_content
        )

        print(

            f"Parsed using primary model: {GROQ_PRIMARY_MODEL}"
        )

        time.sleep(8)

        return parsed


    except Exception as groq_70b_error:

        error_message = str(

            groq_70b_error

        ).lower()


        print(

            f"Primary model {GROQ_PRIMARY_MODEL} failed: "
            f"{groq_70b_error}"
        )


        wait_time = extract_retry_wait(

            error_message
        )

        print(

            f"Waiting {wait_time}s "
            f"before fallback..."
        )

        time.sleep(wait_time)


        if any(

            error in error_message

            for error in RECOVERABLE_GROQ_ERRORS
        ):

            print(

                f"Switching to fallback model {GROQ_FALLBACK_MODEL}..."
            )


            try:

                parsed = parse_with_groq(

                    prompt,

                    GROQ_FALLBACK_MODEL
                )

                parsed = normalize_output(

                    parsed
                )

                parsed = apply_taxonomy_normalization(

                    parsed
                )

                parsed = recover_sparse_fields(

                    parsed,

                    markdown_content
                )

                print(

                    f"Parsed using fallback model: {GROQ_FALLBACK_MODEL}"
                )

                time.sleep(8)

                return parsed


            except Exception as groq_8b_error:

                groq_8b_message = str(

                    groq_8b_error

                ).lower()


                print(

                    f"Fallback model {GROQ_FALLBACK_MODEL} failed: "
                    f"{groq_8b_error}"
                )


                wait_time = extract_retry_wait(

                    groq_8b_message
                )

                print(

                    f"Waiting {wait_time}s "
                    f"before Ollama fallback..."
                )

                time.sleep(wait_time)


                if any(

                    error in groq_8b_message

                    for error in RECOVERABLE_GROQ_ERRORS
                ):

                    print(

                        "Switching to Ollama..."
                    )


                    try:

                        parsed = parse_with_ollama(

                            prompt
                        )

                        parsed = normalize_output(

                            parsed
                        )

                        parsed = apply_taxonomy_normalization(

                            parsed
                        )

                        parsed = recover_sparse_fields(

                            parsed,

                            markdown_content
                        )

                        print(

                            "Parsed using Ollama"
                        )

                        return parsed


                    except Exception as ollama_error:

                        print(

                            f"Ollama failed: "
                            f"{ollama_error}"
                        )

                        return EMPTY_RESPONSE


                return EMPTY_RESPONSE


        return EMPTY_RESPONSE
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
