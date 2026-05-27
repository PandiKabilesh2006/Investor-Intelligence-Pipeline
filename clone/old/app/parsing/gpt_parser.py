import json
import time
import re
import ollama

from groq import Groq

from app.config.settings import (
    GROQ_API_KEY
)


# =========================================
# GROQ CLIENT
# =========================================

groq_client = Groq(

    api_key=GROQ_API_KEY
)


# =========================================
# MODELS
# =========================================

OLLAMA_MODEL = "qwen2.5:3b"

GROQ_MODEL = "llama-3.1-8b-instant"


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

    return f"""
You are a venture capital intelligence
extraction system.

Your task is to extract structured
investor information from venture capital,
investment firm, accelerator, or startup
investment ecosystem pages.

Return ONLY valid JSON.

----------------------------------------
SCHEMA
----------------------------------------

{{
  "firm": "",
  "website": "",
  "partners": [],
  "focus_sectors": [],
  "investment_stage": [],
  "portfolio_companies": [],
  "geography": [],
  "contact_links": []
}}

----------------------------------------
CRITICAL RULES
----------------------------------------

- Extract ONLY investor/VC information
- Do NOT hallucinate
- Do NOT explain anything
- Return ONLY valid JSON
- If information is unavailable,
  return empty arrays
- Normalize information carefully

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

Extract ONLY individuals who are explicitly
part of the investment firm's internal
investment team.

The individual should hold an
investment-related role inside the
organization.

Possible roles include:
- Partner
- Managing Partner
- General Partner
- Venture Partner
- Principal
- Investment Director
- Investor

The extracted value must represent
a REAL PERSON.

Only include names when the content
clearly indicates the person belongs
to the investment organization itself.

Do NOT include:
- startup founders
- portfolio company executives
- article authors
- guest writers
- ecosystem participants
- external advisors
- companies
- organizations
- departments
- software names
- concepts
- job functions

If partner information is unclear,
missing, or ambiguous:
return empty array.

Prefer precision over recall.

Never guess missing names.

----------------------------------------
PORTFOLIO COMPANY EXTRACTION
----------------------------------------

Extract ONLY startup/company names
that are part of the firm's portfolio.

Do NOT extract:
- investor firms
- sectors
- people names
- technologies
- article titles

----------------------------------------
CONTACT LINK EXTRACTION
----------------------------------------

Extract relevant investor-related
contact URLs or communication links.

Examples:
- LinkedIn URLs
- Twitter/X URLs
- contact pages
- official email addresses

----------------------------------------
WEBSITE CONTENT
----------------------------------------

{markdown_content[:5000]}
"""


def normalize_output(parsed):

    if not isinstance(parsed, dict):

        return EMPTY_RESPONSE


    # =====================================
    # EXTRACT FIRST FIRM IF VALUE IS LIST OR STRINGIFIED LIST
    # =====================================
    firm_val = parsed.get("firm", "")
    evaluated_list = None

    if isinstance(firm_val, list):
        evaluated_list = firm_val
    elif isinstance(firm_val, str):
        firm_val_stripped = firm_val.strip()
        if (firm_val_stripped.startswith("[") and firm_val_stripped.endswith("]")) or (firm_val_stripped.startswith("{") and "name" in firm_val_stripped):
            try:
                import ast
                evaluated = ast.literal_eval(firm_val_stripped)
                if isinstance(evaluated, list):
                    evaluated_list = evaluated
                elif isinstance(evaluated, dict):
                    evaluated_list = [evaluated]
            except Exception as e:
                print(f"Failed to safely evaluate stringified list/dict in firm field: {e}")
                # Fallback extraction for malformed stringified lists e.g. ['a','ab','ac'a,ab'']
                if firm_val_stripped.startswith("[") and firm_val_stripped.endswith("]"):
                    inner = firm_val_stripped[1:-1].strip()
                    if inner:
                        parts = inner.split(",")
                        if parts:
                            first_part = parts[0].strip()
                            first_part = first_part.strip("'\"").strip()
                            parsed["firm"] = first_part

    if evaluated_list and len(evaluated_list) > 0:
        first_firm = evaluated_list[0]
        if isinstance(first_firm, dict):
            # Extract and assign attributes to the top-level keys
            parsed["firm"] = first_firm.get("name") or first_firm.get("firm") or ""
            if "website" in first_firm:
                parsed["website"] = first_firm["website"]
            if "partners" in first_firm:
                parsed["partners"] = first_firm["partners"]
            if "focus_sectors" in first_firm:
                parsed["focus_sectors"] = first_firm["focus_sectors"]
            if "investment_stage" in first_firm:
                parsed["investment_stage"] = first_firm["investment_stage"]
            if "portfolio_companies" in first_firm:
                parsed["portfolio_companies"] = first_firm["portfolio_companies"]
            if "geography" in first_firm:
                parsed["geography"] = first_firm["geography"]
            if "contact_links" in first_firm:
                parsed["contact_links"] = first_firm["contact_links"]
        elif isinstance(first_firm, str):
            # It's a list of strings, so the first element is the firm name
            parsed["firm"] = first_firm.strip()


    parsed.setdefault("firm", "")

    parsed.setdefault("website", "")

    parsed.setdefault("partners", [])

    parsed.setdefault("focus_sectors", [])

    parsed.setdefault("investment_stage", [])

    parsed.setdefault("portfolio_companies", [])

    parsed.setdefault("geography", [])

    parsed.setdefault("contact_links", [])


    # =====================================
    # ENSURE LIST TYPES
    # =====================================

    for field in [

        "partners",

        "focus_sectors",

        "investment_stage",

        "portfolio_companies",

        "geography",

        "contact_links"
    ]:

        if not isinstance(

            parsed[field],

            list
        ):

            parsed[field] = []


    # =====================================
    # STRING CLEANUP & BRACKET ARTIFACT REMOVAL
    # =====================================

    firm_str = str(parsed.get("firm", "")).strip()

    # Double check if firm string is a list-like bracket representation and extract the first element
    if firm_str.startswith("[") and firm_str.endswith("]"):
        inner = firm_str[1:-1].strip()
        if inner:
            parts = inner.split(",")
            if parts:
                firm_str = parts[0].strip().strip("'\"").strip()
        else:
            firm_str = ""

    firm_str = firm_str.strip("'\"").strip()
    parsed["firm"] = firm_str

    if isinstance(parsed["firm"], list):
        parsed["firm"] = parsed["firm"][0]

    parsed["website"] = str(

        parsed["website"]
    ).strip()


    # =====================================
    # REMOVE EMPTY VALUES
    # =====================================

    for field in [

        "partners",

        "focus_sectors",

        "investment_stage",

        "portfolio_companies",

        "geography",

        "contact_links"
    ]:

        parsed[field] = [

            str(x).strip()

            for x in parsed[field]

            if str(x).strip()
        ]


    return parsed


# =========================================
# HUMAN NAME FILTER
# =========================================

def filter_partner_names(partners):

    filtered = []


    for partner in partners:

        partner = str(partner).strip()


        if not re.match(

            r"^[A-Z][a-z]+(?:\s[A-Z][a-z]+)+$",

            partner
        ):

            continue


        filtered.append(partner)


    return list(set(filtered))


# =========================================
# CONTACT LINK FILTER
# =========================================

def filter_contact_links(links):

    filtered = []


    for link in links:

        link = str(link).strip()


        if (

            "linkedin.com" in link

            or

            "twitter.com" in link

            or

            "x.com" in link

            or

            "mailto:" in link

            or

            "/contact" in link
        ):

            filtered.append(link)


    return list(set(filtered))


# =========================================
# TAXONOMY NORMALIZATION
# =========================================

def apply_taxonomy_normalization(parsed):

    # =====================================
    # SECTOR NORMALIZATION
    # =====================================

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

        "ai infrastructure": "Artificial Intelligence"
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

        set(normalized_sectors)
    )


    # =====================================
    # STAGE NORMALIZATION
    # =====================================

    stage_mapping = {

        "pre seed": "Pre-Seed",

        "early-stage": "Seed",

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

        set(normalized_stages)
    )


    # =====================================
    # GEOGRAPHY NORMALIZATION
    # =====================================

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

        set(normalized_geography)
    )


    # =====================================
    # PARTNER FILTERING
    # =====================================

    parsed["partners"] = filter_partner_names(

        parsed["partners"]
    )


    # =====================================
    # CONTACT LINK FILTERING
    # =====================================

    parsed["contact_links"] = filter_contact_links(

        parsed["contact_links"]
    )


    return parsed


# =========================================
# JSON EXTRACTION
# =========================================

def extract_json(text):
    cleaned = text.replace("```json", "").replace("```", "").strip()

    # Gather all top-level {...} candidates using brace matching
    candidates = []
    stack = 0
    start = None
    for i, ch in enumerate(cleaned):
        if ch == "{":
            if stack == 0:
                start = i
            stack += 1
        elif ch == "}":
            if stack > 0:
                stack -= 1
                if stack == 0 and start is not None:
                    candidates.append(cleaned[start:i+1])
                    start = None

    def repair_text(s: str) -> str:
        # remove JS-style comments
        s = re.sub(r"//.*?$|/\*.*?\*/", "", s, flags=re.DOTALL | re.MULTILINE)
        # remove trailing commas before } or ]
        s = re.sub(r",\s*(?=[}\]])", "", s)
        # replace lone single-quoted strings with double quotes
        s = re.sub(r"(?<!\")'([^']*)'(?!\")", r'"\1"', s)
        return s

    # Try parsing candidates (try longest first)
    for cand in sorted(candidates, key=len, reverse=True):
        try:
            return json.loads(cand)
        except Exception:
            # attempt simple repairs and retry
            try:
                repaired = repair_text(cand)
                return json.loads(repaired)
            except Exception:
                # continue to next candidate
                continue

    # Fallback: try to parse any JSON-like object via regex as last resort
    json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except Exception:
            try:
                return json.loads(repair_text(json_match.group(0)))
            except Exception:
                pass

    raise ValueError("No JSON object found or unable to parse JSON")


# =========================================
# OLLAMA PARSER
# =========================================

def parse_with_ollama(prompt):
    import urllib.request
    import json
    
    url = "http://127.0.0.1:11434/api/chat"
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": False,
        "options": {
            "temperature": 0
        }
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    with urllib.request.urlopen(req, timeout=60.0) as response:
        res_data = json.loads(response.read().decode("utf-8"))
        output = res_data["message"]["content"]
        
    return extract_json(output)


# =========================================
# GROQ PARSER
# =========================================

def parse_with_groq(prompt):

    response = groq_client.chat.completions.create(

        model=GROQ_MODEL,

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
    # TRY GROQ FIRST
    # =====================================

    for attempt in range(3):

        try:

            parsed = parse_with_groq(

                prompt
            )

            parsed = normalize_output(

                parsed
            )

            parsed = apply_taxonomy_normalization(

                parsed
            )

            print(

                "Parsed using Groq"
            )

            return parsed


        except Exception as groq_error:

            print(

                f"Groq failed (attempt {attempt + 1}/3): "
                f"{groq_error}"
            )

            if attempt < 2:
                time.sleep(2)


    # =====================================
    # FALLBACK TO OLLAMA
    # =====================================

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

        print(

            "Parsed using Ollama fallback"
        )

        return parsed


    except Exception as ollama_error:

        print(

            f"Ollama fallback failed: "
            f"{ollama_error}"
        )


    # =====================================
    # FINAL FALLBACK
    # =====================================

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