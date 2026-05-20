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

    "focus_sectors": [],

    "investment_stage": [],

    "geography": [],

    "partners": []
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
  "focus_sectors": [],
  "investment_stage": [],
  "geography": [],
  "partners": []
}}

----------------------------------------
CRITICAL RULES
----------------------------------------

- Extract ONLY investor/VC information
- Do NOT hallucinate
- Do NOT explain
- Return ONLY JSON
- If unavailable, return empty arrays
- Normalize data carefully

----------------------------------------
FOCUS SECTOR TAXONOMY
----------------------------------------

Allowed values:

- Artificial Intelligence
- Enterprise AI
- B2B SaaS
- Voice AI

Map similar concepts carefully.

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
- buyouts → Growth Stage

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

Extract ONLY REAL HUMAN NAMES.

Allowed partner roles:
- Partner
- Managing Partner
- General Partner
- Investment Partner
- Founding Partner

GOOD EXAMPLES:
- Marc Andreessen
- Ben Horowitz
- Alfred Lin

BAD EXAMPLES:
- Human Resources
- Scaling Up
- End-to-End Sales Process
- Sequoia Capital
- Andreessen Horowitz

Do NOT extract:
- VC firm names
- startup names
- portfolio companies
- article authors
- departments
- concepts
- job functions

If no real partner names exist:
return empty array.

----------------------------------------
WEBSITE CONTENT
----------------------------------------

{markdown_content[:5000]}
"""


# =========================================
# OUTPUT NORMALIZATION
# =========================================

def normalize_output(parsed):

    if not isinstance(parsed, dict):

        return EMPTY_RESPONSE


    parsed.setdefault("firm", "")

    parsed.setdefault("website", "")

    parsed.setdefault("focus_sectors", [])

    parsed.setdefault("investment_stage", [])

    parsed.setdefault("geography", [])

    parsed.setdefault("partners", [])


    # =====================================
    # ENSURE LIST TYPES
    # =====================================

    for field in [

        "focus_sectors",

        "investment_stage",

        "geography",

        "partners"
    ]:

        if not isinstance(

            parsed[field],

            list
        ):

            parsed[field] = []


    # =====================================
    # STRING CLEANUP
    # =====================================

    parsed["firm"] = str(

        parsed["firm"]
    ).strip()


    parsed["website"] = str(

        parsed["website"]
    ).strip()


    # =====================================
    # REMOVE EMPTY VALUES
    # =====================================

    for field in [

        "focus_sectors",

        "investment_stage",

        "geography",

        "partners"
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


        # =====================================
        # MUST LOOK LIKE HUMAN NAME
        # =====================================

        if not re.match(

            r"^[A-Z][a-z]+(?:\s[A-Z][a-z]+)+$",

            partner
        ):

            continue


        filtered.append(partner)


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


    # =====================================
    # NON-GREEDY JSON EXTRACTION
    # =====================================

    json_match = re.search(

        r"\{.*?\}",

        cleaned,

        re.DOTALL
    )


    if not json_match:

        raise ValueError(

            "No JSON object found"
        )


    json_text = json_match.group(0)


    return json.loads(json_text)


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
    # TRY OLLAMA FIRST
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

            "Parsed using Ollama"
        )

        return parsed


    except Exception as ollama_error:

        print(

            f"Ollama failed: "
            f"{ollama_error}"
        )


    # =====================================
    # FALLBACK TO GROQ
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

                f"Groq failed: "
                f"{groq_error}"
            )

            time.sleep(2)


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