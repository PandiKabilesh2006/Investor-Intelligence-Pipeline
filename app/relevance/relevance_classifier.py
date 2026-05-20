import json
import time

from groq import Groq

from app.config.settings import (
    GROQ_API_KEY
)


client = Groq(

    api_key=GROQ_API_KEY
)


def classify_investor_relevance(

    query,

    title,

    url,

    snippet
):

    prompt = f"""
You are an investor intelligence retrieval system.

Your task is to determine whether
a search result is likely to be:

- a venture capital firm
- an investment firm
- an investor website
- a portfolio page
- a VC thesis page
- a startup investment platform

IMPORTANT:
Reject:
- news articles
- media pages
- rankings
- blogs
- podcasts
- educational pages
- random startup websites
- unrelated SaaS companies

User Query:
{query}

Search Result Title:
{title}

Search Result URL:
{url}

Search Result Snippet:
{snippet}

Return ONLY valid JSON:

{{
  "is_relevant": true,
  "confidence": 0.95,
  "reason": ""
}}
"""


    for _ in range(3):

        try:

            response = client.chat.completions.create(

                model="llama-3.3-70b-versatile",

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


            return json.loads(output)


        except Exception:

            time.sleep(2)


    return {

        "is_relevant": False,

        "confidence": 0.0,

        "reason": "classification_failed"
    }