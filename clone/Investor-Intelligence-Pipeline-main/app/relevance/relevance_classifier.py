import json
import time
import re
import ollama

from groq import Groq

from app.config.settings import (
    GROQ_API_KEY
)

from app.utils.groq_circuit import (
    is_recoverable_groq_error,
    record_groq_70b_rate_limit_failure,
    should_use_groq_70b,
)


# =========================================
# GROQ CLIENT
# =========================================

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


# =========================================
# PROMPT BUILDER
# =========================================

def build_prompt(

    query,

    title,

    url,

    snippet
):

    return f"""
You are an investor intelligence retrieval system.

Your task is to determine whether
a search result contains useful:

- venture capital intelligence
- startup funding intelligence
- investor ecosystem intelligence
- portfolio intelligence
- startup investment intelligence

The PRIMARY GOAL is:
MAXIMUM INVESTOR DISCOVERY.

IMPORTANT:

A page DOES NOT need to be an
official VC homepage to be valuable.

Many useful investor intelligence sources are:
- investor directories
- curated investor lists
- startup ecosystem databases
- accelerator pages
- VC portfolio pages
- investment theses
- funding reports
- AI startup ecosystem pages
- venture studio pages
- angel investor platforms
- startup funding platforms

----------------------------------------
HIGH VALUE SOURCES
----------------------------------------

Strongly accept:

- venture capital firms
- investment funds
- VC portfolio pages
- investor directories
- startup funding databases
- curated VC lists
- accelerator investor pages
- AI investor ecosystem pages
- SaaS investor lists
- startup ecosystem intelligence
- funding network pages
- venture studios
- angel investor networks
- early-stage investment platforms
- investment thesis pages
- AI infrastructure investment pages
- enterprise AI investment pages

----------------------------------------
REJECT ONLY
----------------------------------------

Reject ONLY if the page is clearly unrelated:

- ecommerce stores
- celebrity news
- sports
- entertainment
- generic spam
- unrelated SaaS products
- unrelated businesses
- unrelated media/news
- gambling/adult content
- random irrelevant websites

DO NOT over-filter.

False positives are acceptable.
False negatives are dangerous.

It is MUCH BETTER to keep
potentially useful investor intelligence
than accidentally reject valuable sources.

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
Extremely strong investor relevance

0.75 - 0.89
Strong investor ecosystem relevance

0.60 - 0.74
Potentially valuable investor intelligence

0.40 - 0.59
Weak but maybe useful startup ecosystem content

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

    if should_use_groq_70b():

        try:

            parsed = classify_with_groq(prompt, GROQ_PRIMARY_MODEL)

            print("Classification using Groq 70B")

            time.sleep(8)

            return parsed

        except Exception as groq_70b_error:

            error_message = str(groq_70b_error).lower()

            print(f"Groq 70B failed: {groq_70b_error}")

            if not is_recoverable_groq_error(error_message):

                return FALLBACK_RESPONSE

            record_groq_70b_rate_limit_failure()

            wait_time = extract_retry_wait(error_message)

            print(f"Waiting {wait_time}s before fallback...")

            time.sleep(wait_time)

    else:

        print(
            "Groq 70B skipped (rate-limit circuit open); using 8B directly."
        )

    return _classify_with_groq_8b_then_ollama(prompt)