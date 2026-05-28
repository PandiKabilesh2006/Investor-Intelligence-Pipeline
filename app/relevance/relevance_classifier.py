import json
import time
import re
import ollama

from urllib.parse import urlparse

from groq import Groq
from openai import OpenAI

from app.config.settings import (
    GROQ_API_KEY,
    OPENAI_API_KEY,
    OPENAI_MODEL
)

from app.utils.groq_circuit import (
    is_recoverable_groq_error,
    record_groq_70b_rate_limit_failure,
    should_use_groq_70b,
)
from app.review_feedback import format_review_examples_for_prompt


# =========================================
# LLM CLIENTS
# =========================================

openai_client = OpenAI(

    api_key=OPENAI_API_KEY
) if OPENAI_API_KEY else None

client = Groq(

    api_key=GROQ_API_KEY,

    max_retries=0,

    timeout=30.0
)


# =========================================
# MODELS
# =========================================

GROQ_PRIMARY_MODEL = "llama-3.3-70b-versatile"

GROQ_FALLBACK_MODEL = "llama-3.1-8b-instant"

OLLAMA_MODEL = "qwen2.5:3b"


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
# FALLBACK RESPONSE
# =========================================

FALLBACK_RESPONSE = {

    "relevance_tier": "reject",

    "is_relevant": False,

    "confidence": 0.0,

    "reason": "classification_failed"
}


POSITIVE_PATTERNS = {
    "firm_site": [
        "venture capital",
        "vc firm",
        "investment firm",
        "seed fund",
        "growth fund",
        "early stage fund",
        "we invest",
        "our investments",
    ],
    "people": [
        "team",
        "people",
        "partners",
        "general partner",
        "managing partner",
        "investment team",
    ],
    "portfolio": [
        "portfolio",
        "companies",
        "investments",
        "backed by",
        "our companies",
    ],
    "strategy": [
        "thesis",
        "focus",
        "sectors",
        "stage",
        "seed",
        "series a",
        "b2b saas",
        "artificial intelligence",
        "enterprise ai",
    ],
    "directory": [
        "investor list",
        "vc list",
        "top investors",
        "venture capital firms",
        "startup investors",
        "funding database",
    ],
}


NEGATIVE_PATTERNS = [
    "blog post",
    "blog archive",
    "company blog",
    "job opening",
    "careers",
    "daily news",
    "editorial",
    "newsletter",
    "press release",
    "sponsored content",
    "coupon",
    "casino",
    "sports",
    "celebrity",
    "product pricing",
    "customer support",
    "terms of service",
    "privacy policy",
    "login",
    "sign up",
    "government of",
    "ministry of",
    "investment promotion agency",
    "economic development agency",
    "foreign direct investment",
    "ease of doing business",
    "policy think tank",
    "investment opportunities",
]


NOISY_DOMAINS = [
    "bloomberg.com",
    "businessinsider.com",
    "cnbc.com",
    "economictimes.indiatimes.com",
    "forbes.com",
    "fortune.com",
    "medium.com",
    "moneycontrol.com",
    "nytimes.com",
    "reuters.com",
    "substack.com",
    "wsj.com",
]


NOISY_PATH_PARTS = {
    "blog",
    "blogs",
    "news",
    "article",
    "articles",
    "press",
    "press-release",
    "press-releases",
    "newsletter",
    "insights",
    "resources",
    "content",
    "events",
}


HIGH_SIGNAL_PATH_PARTS = {
    "about",
    "team",
    "people",
    "partners",
    "portfolio",
    "companies",
    "thesis",
    "focus",
    "investment",
    "investments",
}


RELEVANCE_JSON_SCHEMA = {

    "name": "investor_relevance_classification",

    "strict": True,

    "schema": {

        "type": "object",

        "additionalProperties": False,

        "properties": {

            "relevance_tier": {

                "type": "string"
            },

            "is_relevant": {

                "type": "boolean"
            },

            "confidence": {

                "type": "number"
            },

            "reason": {

                "type": "string"
            }
        },

        "required": [

            "relevance_tier",

            "is_relevant",

            "confidence",

            "reason"
        ]
    }
}


# =========================================
# PROMPT BUILDER
# =========================================

def build_prompt(

    query,

    title,

    url,

    snippet
):
    reviewed_examples = format_review_examples_for_prompt(
        query_text=" ".join([query or "", title or "", url or "", snippet or ""]),
        limit=5,
    )

    return f"""
You are an investor intelligence retrieval system.

Your task is to decide whether a search result is likely
to produce structured investor data for this schema:

- firm name
- website
- partners / investment team
- focus sectors
- investment stage
- portfolio companies
- geography / investment region
- contact or social links

The PRIMARY GOAL is accurate investor discovery.
Prefer sources that help extract one or more of those fields.

----------------------------------------
HIGH VALUE SOURCES
----------------------------------------

Strongly accept:

- official venture capital / investment firm websites
- official about, team, people, partner, portfolio, thesis,
  focus, companies, or contact pages
- credible investor directories and curated investor lists
- startup funding databases with investor profiles
- venture studio or accelerator investor pages
- investment thesis/focus pages that mention sectors,
  stages, regions, or portfolio companies
- recent funding articles only when they identify real
  investors/firms and useful source links

----------------------------------------
LOW VALUE OR REJECT
----------------------------------------

Reject or score low when the page cannot produce structured
investor records:

- ecommerce stores
- celebrity news
- sports
- entertainment
- generic spam
- unrelated SaaS products
- unrelated businesses
- generic news pages that only mention one funding event
  without investor profile details
- media/news outlets and standalone blog posts, unless they
  are clearly structured investor directories or official VC
  firm pages with extractable team/portfolio/focus data
- startup product pages that are not investor/fund pages
- portfolio company pages unless they clearly list investors
- government portals, ministries, policy bodies, public-sector
  investment promotion agencies, and economic development sites
  that promote a country/region rather than operate as a real
  investment fund or VC firm
- gambling/adult content
- random irrelevant websites

Do not accept a page only because it contains the word
"startup" or "AI". It must be investor/funding/VC related.

----------------------------------------
HUMAN REVIEW FEEDBACK
----------------------------------------

Use these prior human-reviewed examples as project-specific
guidance. Follow the pattern of human labels when the new result
is similar.

{reviewed_examples}

----------------------------------------
USER QUERY
----------------------------------------

{query}

----------------------------------------
SEARCH RESULT TITLE
----------------------------------------

{title}

----------------------------------------
SEARCH RESULT URL
----------------------------------------

{url}

----------------------------------------
SEARCH RESULT SNIPPET
----------------------------------------

{snippet}

----------------------------------------
SCORING GUIDELINES
----------------------------------------

0.90 - 1.00
Official firm page or direct team/portfolio/thesis page

0.75 - 0.89
Credible directory/profile/list likely to identify investors

0.60 - 0.74
Useful but partial investor data

0.40 - 0.59
Weak, noisy, or indirect investor content

Below 0.40
Likely irrelevant

----------------------------------------
RETURN FORMAT
----------------------------------------

Return ONLY valid JSON:

{{
  "relevance_tier": "high",
  "is_relevant": true,
  "confidence": 0.95,
  "reason": ""
}}
"""


def classify_with_heuristics(query, title, url, snippet):
    text = " ".join(
        [
            query or "",
            title or "",
            url or "",
            snippet or "",
        ]
    ).lower()

    try:
        parsed_url = urlparse(url)
        hostname = (parsed_url.hostname or "").lower()
        path_parts = {
            part
            for part in re.split(r"[^a-z0-9-]+", parsed_url.path.lower())
            if part
        }
    except Exception:
        hostname = ""
        path_parts = set()

    noisy_domain = any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in NOISY_DOMAINS
    )
    noisy_path = bool(path_parts & NOISY_PATH_PARTS)
    high_signal_path = bool(path_parts & HIGH_SIGNAL_PATH_PARTS)

    if noisy_domain:
        return {
            "relevance_tier": "reject",
            "is_relevant": False,
            "confidence": 0.15,
            "reason": "noisy_media_domain",
        }

    if noisy_path:
        return {
            "relevance_tier": "reject",
            "is_relevant": False,
            "confidence": 0.25,
            "reason": "noisy_content_path",
        }

    if any(pattern in text for pattern in NEGATIVE_PATTERNS):
        return {
            "relevance_tier": "reject",
            "is_relevant": False,
            "confidence": 0.20,
            "reason": "negative_keyword_match",
        }

    score = 0.0
    matched_groups = []

    for group, patterns in POSITIVE_PATTERNS.items():
        if any(pattern in text for pattern in patterns):
            matched_groups.append(group)
            score += 0.18

    if high_signal_path:
        score += 0.15
        matched_groups.append("high_signal_path")

    if "investor" in text or "venture capital" in text or " vc " in f" {text} ":
        score += 0.20

    confidence = min(score, 0.92)
    normalized = normalize_output(
        {
            "confidence": confidence,
            "is_relevant": confidence >= 0.55,
            "reason": "heuristic:" + ",".join(sorted(set(matched_groups))),
        }
    )
    normalized["is_relevant"] = confidence >= 0.55

    return normalized


# =========================================
# OUTPUT NORMALIZATION
# =========================================

def normalize_output(parsed):

    if not isinstance(parsed, dict):

        return FALLBACK_RESPONSE


    parsed.setdefault(
        "relevance_tier",
        "reject"
    )

    parsed.setdefault(
        "is_relevant",
        False
    )

    parsed.setdefault(
        "confidence",
        0.0
    )

    parsed.setdefault(
        "reason",
        ""
    )


    try:

        confidence = float(
            parsed.get(
                "confidence",
                0.0
            )
        )

    except Exception:

        confidence = 0.0


    parsed["confidence"] = confidence


    parsed["is_relevant"] = (

        confidence >= 0.40
    )


    if confidence >= 0.90:

        parsed["relevance_tier"] = (
            "high"
        )

    elif confidence >= 0.70:

        parsed["relevance_tier"] = (
            "medium"
        )

    elif confidence >= 0.40:

        parsed["relevance_tier"] = (
            "low"
        )

    else:

        parsed["relevance_tier"] = (
            "reject"
        )


    parsed["reason"] = str(
        parsed.get(
            "reason",
            ""
        )
    ).strip()


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
# OLLAMA CLASSIFIER
# =========================================

def classify_with_ollama(prompt):

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


    parsed = extract_json(output)


    return normalize_output(parsed)


# =========================================
# OPENAI CLASSIFIER
# =========================================

def classify_with_openai(prompt):

    if not openai_client:

        raise RuntimeError(

            "OPENAI_API_KEY is not configured"
        )


    response = openai_client.chat.completions.create(

        model=OPENAI_MODEL,

        temperature=0,

        response_format={

            "type": "json_schema",

            "json_schema": RELEVANCE_JSON_SCHEMA
        },

        messages=[

            {
                "role": "system",

                "content": (
                    "Classify investor-search relevance and return only "
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

            f"OpenAI refused relevance classification: {refusal}"
        )


    parsed = extract_json(

        message.content
    )


    return normalize_output(parsed)


# =========================================
# GROQ CLASSIFIER
# =========================================

def classify_with_groq(

    prompt,

    model_name
):

    response = client.chat.completions.create(

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


    parsed = extract_json(output)


    return normalize_output(parsed)


def _classify_with_groq_8b_then_ollama(prompt):

    print("Switching to Groq 8B...")

    try:

        parsed = classify_with_groq(prompt, GROQ_FALLBACK_MODEL)

        print("Classification using Groq 8B")

        time.sleep(8)

        return parsed

    except Exception as groq_8b_error:

        groq_8b_message = str(groq_8b_error).lower()

        print(f"Groq 8B failed: {groq_8b_error}")

        wait_time = extract_retry_wait(groq_8b_message)

        print(f"Waiting {wait_time}s before Ollama fallback...")

        time.sleep(wait_time)

        if not is_recoverable_groq_error(groq_8b_message):

            return FALLBACK_RESPONSE

        print("Switching to Ollama...")

        try:

            parsed = classify_with_ollama(prompt)

            print("Classification using Ollama")

            return parsed

        except Exception as ollama_error:

            print(f"Ollama failed: {ollama_error}")

            return FALLBACK_RESPONSE


def _classify_with_groq_70b_then_8b_then_ollama(prompt):

    if should_use_groq_70b():

        try:

            parsed = classify_with_groq(prompt, GROQ_PRIMARY_MODEL)

            print("Classification using Groq 70B")

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


    return _classify_with_groq_8b_then_ollama(prompt)


# =========================================
# INVESTOR RELEVANCE CLASSIFIER
# =========================================

def classify_investor_relevance(

    query,

    title,

    url,

    snippet
):

    prompt = build_prompt(

        query,

        title,

        url,

        snippet
    )

    try:

        parsed = classify_with_openai(prompt)

        print(f"Classification using OpenAI {OPENAI_MODEL}")

        return parsed

    except Exception as openai_error:

        print(f"OpenAI classification failed: {openai_error}")

        print("Switching to Groq 70B...")

    parsed = _classify_with_groq_70b_then_8b_then_ollama(prompt)

    if parsed.get("reason") == "classification_failed":

        return classify_with_heuristics(

            query,

            title,

            url,

            snippet
        )

    return parsed
