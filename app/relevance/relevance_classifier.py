import json
import time
import re
import ollama

from groq import Groq
from openai import OpenAI

from app.config.settings import (
    GROQ_API_KEY,
    GROQ_PRIMARY_MODEL,
    GROQ_FALLBACK_MODEL,
    OPENAI_API_KEY,
    OPENAI_PRIMARY_MODEL
)
from app.prompts.loader import load_prompt


# =========================================
# OPENAI CLIENT
# =========================================

openai_client = OpenAI(
    api_key=OPENAI_API_KEY,
    max_retries=0,
    timeout=30.0
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

# Imported models configured from settings

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

    "reason": "classification_failed",

    "source_type": "unknown"
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
    template = load_prompt("relevance_prompt.txt")
    return template.format(
        query=query,
        title=title,
        url=url,
        snippet=snippet
    )


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


    # Normalize source_type
    valid_source_types = {
        "investor_profile",
        "investor_mention",
        "investor_directory",
        "unknown"
    }

    source_type = str(
        parsed.get("source_type", "investor_mention")
    ).strip().lower()

    if source_type not in valid_source_types:
        source_type = "investor_mention"

    parsed["source_type"] = source_type


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

def classify_with_openai(
    prompt,
    model_name
):
    response = openai_client.chat.completions.create(
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


# =========================================
# INVESTOR RELEVANCE CLASSIFIER
# =========================================

def classify_investor_relevance(

    query,

    title,

    url,

    snippet
):

    # =====================================
    # LIGHTWEIGHT KEYWORD PRE-FILTER
    # =====================================
    text_to_check = f"{query} {title} {url} {snippet}".lower()
    investor_keywords = [
        "invest", "vc", "venture", "capital", "fund", "seed", "equity", 
        "accelerator", "incubator", "angel", "portfolio", "startup", "partner", 
        "founder", "backer", "allocator", "syndicate", "financing", "raising",
        "b2b", "saas", "artificial intelligence", "voice ai", "dealroom", 
        "crunchbase", "pitchbook", "y combinator", "techstars"
    ]
    if not any(kw in text_to_check for kw in investor_keywords):
        print(f"Skipping LLM relevance classification for: {url} (pre-filter fail)")
        return {
            "relevance_tier": "reject",
            "is_relevant": False,
            "confidence": 0.0,
            "reason": "lightweight_keyword_pre_filter_failed"
        }

    prompt = build_prompt(

        query,

        title,

        url,

        snippet
    )


    # =====================================
    # 1. PRIMARY: OPENAI (gpt-4o)
    # =====================================
    if OPENAI_API_KEY:
        try:
            parsed = classify_with_openai(prompt, OPENAI_PRIMARY_MODEL)
            print(f"Classification using OpenAI primary model: {OPENAI_PRIMARY_MODEL}")
            return parsed
        except Exception as openai_error:
            print(f"OpenAI model {OPENAI_PRIMARY_MODEL} failed: {openai_error}")
            print("Switching to Groq primary model fallback...")

    # =====================================
    # 2. FALLBACK 1: GROQ 70B
    # =====================================
    try:
        parsed = classify_with_groq(prompt, GROQ_PRIMARY_MODEL)
        print(f"Classification using Groq primary model: {GROQ_PRIMARY_MODEL}")
        time.sleep(8)
        return parsed
    except Exception as groq_70b_error:
        error_message = str(groq_70b_error).lower()
        print(f"Groq primary model {GROQ_PRIMARY_MODEL} failed: {groq_70b_error}")
        wait_time = extract_retry_wait(error_message)
        print(f"Waiting {wait_time}s before Groq fallback...")
        time.sleep(wait_time)

        # =====================================
        # 3. FALLBACK 2: GROQ 8B
        # =====================================
        try:
            parsed = classify_with_groq(prompt, GROQ_FALLBACK_MODEL)
            print(f"Classification using Groq fallback model: {GROQ_FALLBACK_MODEL}")
            time.sleep(8)
            return parsed
        except Exception as groq_8b_error:
            groq_8b_message = str(groq_8b_error).lower()
            print(f"Groq fallback model {GROQ_FALLBACK_MODEL} failed: {groq_8b_error}")
            wait_time = extract_retry_wait(groq_8b_message)
            print(f"Waiting {wait_time}s before Ollama fallback...")
            time.sleep(wait_time)

            # =====================================
            # 4. FALLBACK 3: OLLAMA
            # =====================================
            try:
                print("Switching to Ollama...")
                parsed = classify_with_ollama(prompt)
                print("Classification using Ollama")
                return parsed
            except Exception as ollama_error:
                print(f"Ollama failed: {ollama_error}")
                return FALLBACK_RESPONSE