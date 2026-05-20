import json
import time

from groq import Groq

from app.config.settings import (
    GROQ_API_KEY
)


# =========================================
# GROQ CLIENT
# =========================================

client = Groq(

    api_key=GROQ_API_KEY
)


# =========================================
# MODEL
# =========================================

MODEL_NAME = "llama-3.1-8b-instant"


# =========================================
# INVESTOR RELEVANCE CLASSIFIER
# =========================================

def classify_investor_relevance(

    query,

    title,

    url,

    snippet
):

    prompt = f"""
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
    # RETRY LOGIC
    # =========================================

    for attempt in range(3):

        try:

            response = client.chat.completions.create(

                model=MODEL_NAME,

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


            parsed = json.loads(output)


            # =========================================
            # SAFE DEFAULTS
            # =========================================

            parsed.setdefault(

                "relevance_tier",
                "low"
            )

            parsed.setdefault(

                "confidence",
                0.0
            )

            parsed.setdefault(

                "reason",
                ""
            )


            confidence = float(

                parsed.get(
                    "confidence",
                    0.0
                )
            )


            # =========================================
            # SOFT RECALL-FIRST FILTERING
            # =========================================

            parsed["is_relevant"] = (

                confidence >= 0.40
            )


            # =========================================
            # AUTO-TIER NORMALIZATION
            # =========================================

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


            return parsed


        except Exception as error:

            print(

                f"Classification failed: "
                f"{error}"
            )

            time.sleep(2)


    # =========================================
    # FALLBACK RESPONSE
    # =========================================

    return {

        "relevance_tier": "reject",

        "is_relevant": False,

        "confidence": 0.0,

        "reason": "classification_failed"
    }